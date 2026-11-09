"""Translate microphone speech into audio played through headphones.

Install dependencies: python -m pip install -r requirements.txt
Set GEMINI_API_KEY, then run: python livevoicetranslater.py --target-language es
Use --list-devices to find device IDs and --input-device / --output-device
to select a headset. Press Ctrl+C to stop.
"""

import argparse
import asyncio
import contextlib
import os
import queue
import time
from typing import Any

import sounddevice as sd
from google import genai
from google.genai import types


MODEL = "gemini-3.5-live-translate-preview"
# Live Translate accepts 16 kHz PCM and returns 24 kHz PCM; both streams are mono.
INPUT_RATE = 16000
OUTPUT_RATE = 24000
INPUT_FRAMES = 1600
OUTPUT_FRAMES = 2400
STATUS_INTERVAL = 5.0


def device_id(value: str) -> int | str:
    return int(value) if value.isdecimal() else value


class AudioBridge:
    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        # Capture is consumed by asyncio; playback is shared with the audio callback thread.
        self.input_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=10)
        self.output_queue: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self.error: asyncio.Future[None] = self.loop.create_future()
        self.pending_output = bytearray()
        self.last_capture_status: float | None = None
        self.last_send_status: float | None = None
        self.last_playback_status: float | None = None

    @staticmethod
    def status_due(last_status: float | None, now: float) -> bool:
        return last_status is None or now - last_status >= STATUS_INTERVAL

    def fail(self, message: str) -> None:
        if not self.error.done():
            self.error.set_exception(RuntimeError(message))

    def enqueue_input(self, data: bytes) -> None:
        try:
            self.input_queue.put_nowait(data)
        except asyncio.QueueFull:
            self.fail("Microphone audio is arriving faster than it can be sent.")
            return
        now = time.monotonic()
        if self.status_due(self.last_capture_status, now):
            self.last_capture_status = now
            print("[Microphone] Audio captured (may include silence).", flush=True)

    def report_sent_audio(self) -> None:
        now = time.monotonic()
        if self.status_due(self.last_send_status, now):
            self.last_send_status = now
            print("[Microphone] Audio sent to Gemini.", flush=True)

    @staticmethod
    def report_playback() -> None:
        print("[Playback] Translated audio sent to the output device.", flush=True)

    def input_callback(self, indata: Any, _frames: int, _time: Any, status: Any) -> None:
        if status:
            self.loop.call_soon_threadsafe(self.fail, f"Microphone stream error: {status}")
        # Copy the callback buffer before scheduling work on the event-loop thread.
        self.loop.call_soon_threadsafe(self.enqueue_input, bytes(indata))

    def output_callback(self, outdata: Any, frames: int, _time: Any, status: Any) -> None:
        if status:
            self.loop.call_soon_threadsafe(self.fail, f"Headphone stream error: {status}")
        byte_count = frames * 2
        while len(self.pending_output) < byte_count:
            try:
                self.pending_output.extend(self.output_queue.get_nowait())
            except queue.Empty:
                break
        available = min(len(self.pending_output), byte_count)
        # Fill the entire device buffer, padding with silence when audio is unavailable.
        outdata[:] = self.pending_output[:available] + bytes(byte_count - available)
        del self.pending_output[:available]
        if available:
            now = time.monotonic()
            if self.status_due(self.last_playback_status, now):
                self.last_playback_status = now
                self.loop.call_soon_threadsafe(self.report_playback)

    def enqueue_output(self, data: bytes) -> None:
        try:
            self.output_queue.put_nowait(data)
        except queue.Full as exc:
            raise RuntimeError("Translated audio is arriving faster than it can be played.") from exc


async def send_microphone(session: Any, audio: AudioBridge) -> None:
    while True:
        chunk = await audio.input_queue.get()
        await session.send_realtime_input(
            audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={INPUT_RATE}")
        )
        audio.report_sent_audio()


async def receive_translation(session: Any, audio: AudioBridge) -> None:
    while True:
        received = False
        # receive() can end after a turn; start another receive for subsequent turns.
        async for response in session.receive():
            received = True
            content = response.server_content
            if not content:
                continue
            if content.input_transcription and content.input_transcription.text:
                print(f"[Source] {content.input_transcription.text}", flush=True)
            if content.output_transcription and content.output_transcription.text:
                print(f"[Translation] {content.output_transcription.text}", flush=True)
            if content.model_turn and content.model_turn.parts:
                for part in content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        audio.enqueue_output(part.inline_data.data)
        if not received:
            raise RuntimeError("The Live API stopped sending responses.")


async def run_translation(
    target_language: str, input_device: int | str | None, output_device: int | str | None
) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set the GEMINI_API_KEY environment variable before running this example.")

    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        translation_config=types.TranslationConfig(
            target_language_code=target_language,
            echo_target_language=True,
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1beta"),
    )
    audio = AudioBridge()

    print(f"Connecting to {MODEL}...")
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        # ExitStack closes the input stream even if opening the output stream fails.
        with contextlib.ExitStack() as streams:
            streams.enter_context(sd.RawInputStream(
                samplerate=INPUT_RATE,
                blocksize=INPUT_FRAMES,
                channels=1,
                dtype="int16",
                device=input_device,
                callback=audio.input_callback,
            ))
            try:
                streams.enter_context(sd.RawOutputStream(
                    samplerate=OUTPUT_RATE,
                    blocksize=OUTPUT_FRAMES,
                    channels=1,
                    dtype="int16",
                    device=output_device,
                    callback=audio.output_callback,
                ))
            except (sd.PortAudioError, ValueError) as exc:
                raise RuntimeError(
                    f"Could not open output device {output_device!r}: {exc}. "
                    "Run livevoicetranslater.py --list-devices and select an output device "
                    "with --output-device, or omit the option to use the system default."
                ) from exc
            print(f"Speak into your microphone. Translation: {target_language}. Press Ctrl+C to stop.")
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(send_microphone(session, audio))
                tasks.create_task(receive_translation(session, audio))
                await audio.error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-language", default="es", help="Target language code (default: es).")
    parser.add_argument("--input-device", type=device_id, help="Microphone device ID or name.")
    parser.add_argument("--output-device", type=device_id, help="Headphone device ID or name.")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit.")
    args = parser.parse_args()
    if args.list_devices:
        print(sd.query_devices())
        return
    try:
        asyncio.run(run_translation(args.target_language, args.input_device, args.output_device))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

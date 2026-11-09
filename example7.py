# Translate an audio URL into a local WAV file using Gemini Live and FFmpeg.
import os
import shutil
from google import genai
from google.genai import errors, types
import http.client

# 1. Provide your configuration targets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Set the GEMINI_API_KEY environment variable before running this script.")

client = genai.Client(
        api_key=os.environ['GEMINI_API_KEY'],
        http_options=types.HttpOptions(api_version="v1beta")
    )

MODEL = "gemini-3.5-live-translate-preview"  # @param ["gemini-3.5-live-translate-preview"] {"allow-input": true, "isTemplate": true}

import array
import asyncio
import contextlib
import wave

from google import genai
from google.genai import types

@contextlib.contextmanager
def wave_file(filename, channels=1, rate=24000, sample_width=2):
    # Live Translate output is 24 kHz mono 16-bit PCM.
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        yield wf

async def stream_audio_url(url: str, audio_queue: asyncio.Queue, ffmpeg_path: str, sample_rate: int = 16000, channels: int = 1, chunk_size: int = 1600):
    """Streams audio from an HTTP URL, decoding it via ffmpeg and putting raw PCM bytes into the audio_queue."""
    print(f"\n[Info] Starting audio stream via ffmpeg from: {url}")
    # Spawn ffmpeg to decode stream to raw PCM 16kHz mono 16-bit
    process = await asyncio.create_subprocess_exec(
        ffmpeg_path,
        '-i', url,
        '-f', 's16le',
        '-acodec', 'pcm_s16le',
        '-ar', str(sample_rate),
        '-ac', str(channels),
        '-',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )

    # 1600 samples * 2 bytes/sample (16-bit) = 3200 bytes per chunk
    chunk_size_bytes = chunk_size * 2
    bytes_per_second = sample_rate * 2
    start_time = asyncio.get_event_loop().time()
    bytes_sent = 0

    try:
        while True:
            data = await process.stdout.read(chunk_size_bytes)
            if not data:
                break

            await audio_queue.put(data)
            bytes_sent += len(data)

            # Rate limit to real-time speed (1.0x) so we simulate real mic streaming
            expected_elapsed = bytes_sent / bytes_per_second
            actual_elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = expected_elapsed - actual_elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    except asyncio.CancelledError:
        pass
    finally:
        if process.returncode is None:
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass
        print("\n[Info] Audio stream finished.")

async def send_realtime(session, audio_queue: asyncio.Queue, sample_rate: int = 16000):
    """Sends audio from the input queue to the GenAI session."""
    try:
        while True:
            chunk = await audio_queue.get()
            try:
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=chunk,
                        mime_type=f"audio/pcm;rate={sample_rate}"
                    )
                )
            finally:
                # Balance queue.get() even if sending fails or the task is cancelled.
                audio_queue.task_done()
    except asyncio.CancelledError:
        pass


def log_exception_details(error: BaseException, prefix: str = "  ") -> None:
    # TaskGroup errors can contain nested exception groups.
    if isinstance(error, BaseExceptionGroup):
        for nested_error in error.exceptions:
            log_exception_details(nested_error, prefix)
    else:
        print(f"{prefix}{type(error).__name__}: {error}")


async def run_audio_translation(url: str, target_lang: str):
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError(
            "FFmpeg is required to decode the input audio. Install FFmpeg, add "
            "ffmpeg.exe to your PATH, and restart the terminal."
        )

    # Configure live connection with translation settings
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        translation_config=types.TranslationConfig(
            echo_target_language=True,
            target_language_code=target_lang,
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    audio_queue_input = asyncio.Queue(maxsize=10)
    file_name = 'audio_translation.wav'

    print(f"[Info] Connecting to Gemini Live ({MODEL})...")

    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[Info] Connected successfully. Starting stream...")

            with wave_file(file_name) as wav:
                async def receive_responses():
                    try:
                        async for response in session.receive():
                            server_content = response.server_content
                            if server_content:
                                # Write translated audio chunks to WAV file
                                if server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data and isinstance(part.inline_data.data, bytes):
                                            wav.writeframes(part.inline_data.data)

                                # Print input (source) transcript
                                if server_content.input_transcription and server_content.input_transcription.text:
                                    lang = f" ({server_content.input_transcription.language_code})" if server_content.input_transcription.language_code else ""
                                    print(f"\n[Source{lang}] {server_content.input_transcription.text}", flush=True)

                                # Print output (translated) transcript
                                if server_content.output_transcription and server_content.output_transcription.text:
                                    lang = f" ({server_content.output_transcription.language_code})" if server_content.output_transcription.language_code else ""
                                    print(f"[Translation{lang}] {server_content.output_transcription.text}", flush=True)
                    except asyncio.CancelledError:
                        pass

                async with asyncio.TaskGroup() as tg:
                    # Task 1: Stream original audio from URL to a queue
                    stream_task = tg.create_task(
                        stream_audio_url(url, audio_queue_input, ffmpeg_path)
                    )
                    # Task 2: Upload audio queue to Gemini Live Translate API
                    send_task = tg.create_task(send_realtime(session, audio_queue_input))
                    # Task 3: Receive transcripts and translated audio response chunks
                    receive_task = tg.create_task(receive_responses())

                    # Wait for the audio stream to finish reading
                    await stream_task

                    # Wait for all buffered input chunks to be sent to Gemini
                    await audio_queue_input.join()
                    send_task.cancel()

                    # Give Gemini a few seconds to finish translating the final chunks
                    await asyncio.sleep(4.0)
                    receive_task.cancel()

    except Exception as e:
        print(f"[Error] Live session error: {e}")
        log_exception_details(e)
        raise

    print("\nTranslation complete!")
    print(f"Translated audio saved to {file_name}")

#@title Run Translation { run: "auto" }
# Audio: Gemini Live Translate sample (or enter your own public audio URL)
audio_url = "https://storage.googleapis.com/generativeai-downloads/gemini-cookbook/audio/gemini-live-translate-sample.wav" #@param {type:"string"}
target_lang = "es" #@param {type:"string"}

if __name__ == "__main__":
    asyncio.run(
        run_audio_translation(
            url=audio_url,
            target_lang=target_lang,
        )
    )
import asyncio
import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import livevoicetranslater


class AudioBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_microphone_callback_and_sending(self):
        audio = livevoicetranslater.AudioBridge()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            audio.input_callback(b"\x01\x02", 1, None, None)
            await asyncio.sleep(0)
            session = SimpleNamespace(send_realtime_input=AsyncMock())
            task = asyncio.create_task(livevoicetranslater.send_microphone(session, audio))
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        blob = session.send_realtime_input.call_args.kwargs["audio"]
        self.assertEqual(blob.data, b"\x01\x02")
        self.assertEqual(blob.mime_type, "audio/pcm;rate=16000")
        self.assertIn("Audio captured", output.getvalue())
        self.assertIn("Audio sent to Gemini", output.getvalue())

    async def test_playback_preserves_chunks_and_fills_silence(self):
        audio = livevoicetranslater.AudioBridge()
        audio.enqueue_output(b"\x01\x02\x03\x04\x05\x06")
        first = bytearray(4)
        second = bytearray(4)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            audio.output_callback(first, 2, None, None)
            audio.output_callback(second, 2, None, None)
            await asyncio.sleep(0)
        self.assertEqual(first, b"\x01\x02\x03\x04")
        self.assertEqual(second, b"\x05\x06\x00\x00")
        self.assertEqual(output.getvalue().count("[Playback]"), 1)

    async def test_silence_output_does_not_report_playback(self):
        audio = livevoicetranslater.AudioBridge()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            audio.output_callback(bytearray(4), 2, None, None)
            await asyncio.sleep(0)
        self.assertNotIn("[Playback]", output.getvalue())

    async def test_status_interval_and_initial_event(self):
        self.assertTrue(livevoicetranslater.AudioBridge.status_due(None, 0.0))
        self.assertFalse(livevoicetranslater.AudioBridge.status_due(0.0, 4.99))
        self.assertTrue(livevoicetranslater.AudioBridge.status_due(0.0, 5.0))

    async def test_failed_send_does_not_report_audio_sent(self):
        audio = livevoicetranslater.AudioBridge()
        audio.input_queue.put_nowait(b"\x01\x02")
        session = SimpleNamespace(send_realtime_input=AsyncMock(side_effect=RuntimeError("send failed")))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(RuntimeError, "send failed"):
                await livevoicetranslater.send_microphone(session, audio)
        self.assertNotIn("Audio sent to Gemini", output.getvalue())

    async def test_microphone_overflow_is_reported(self):
        audio = livevoicetranslater.AudioBridge()
        for _ in range(11):
            audio.enqueue_input(b"\x00\x00")
        with self.assertRaisesRegex(RuntimeError, "Microphone audio"):
            await audio.error

    async def test_output_overflow_is_reported(self):
        audio = livevoicetranslater.AudioBridge()
        for _ in range(100):
            audio.enqueue_output(b"\x00\x00")
        with self.assertRaisesRegex(RuntimeError, "Translated audio"):
            audio.enqueue_output(b"\x00\x00")

    async def test_receive_transcription_and_audio(self):
        audio = livevoicetranslater.AudioBridge()
        content = SimpleNamespace(
            input_transcription=SimpleNamespace(text="hello"),
            output_transcription=SimpleNamespace(text="hola"),
            model_turn=SimpleNamespace(
                parts=[SimpleNamespace(inline_data=SimpleNamespace(data=b"\x01\x02"))]
            ),
        )

        class Session:
            calls = 0

            async def receive(self):
                self.calls += 1
                if self.calls == 1:
                    yield SimpleNamespace(server_content=content)

        with contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(RuntimeError, "stopped sending"):
                await livevoicetranslater.receive_translation(Session(), audio)
        self.assertIn("[Source] hello", output.getvalue())
        self.assertIn("[Translation] hola", output.getvalue())
        self.assertEqual(audio.output_queue.get_nowait(), b"\x01\x02")

    async def test_missing_api_key_fails_before_connecting(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                await livevoicetranslater.run_translation("es", None, None)

    async def test_invalid_output_device_reports_selection_and_closes_input(self):
        @contextlib.asynccontextmanager
        async def connect(**kwargs):
            yield object()

        client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        input_stream = MagicMock()
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch.object(livevoicetranslater.genai, "Client", return_value=client),
            patch.object(livevoicetranslater.sd, "RawInputStream", return_value=input_stream),
            patch.object(livevoicetranslater.sd, "RawOutputStream", side_effect=livevoicetranslater.sd.PortAudioError("Invalid device")),
        ):
            with self.assertRaisesRegex(RuntimeError, r"output device 999.*--list-devices"):
                await livevoicetranslater.run_translation("es", 1, 999)
        input_stream.__exit__.assert_called_once()

    async def test_session_config_and_cleanup_after_receive_error(self):
        class Session:
            async def receive(self):
                raise RuntimeError("connection lost")
                yield

        @contextlib.asynccontextmanager
        async def connect(**kwargs):
            self.assertEqual(kwargs["model"], livevoicetranslater.MODEL)
            self.assertEqual(kwargs["config"].translation_config.target_language_code, "fr")
            yield Session()

        client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        input_stream = MagicMock()
        output_stream = MagicMock()
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch.object(livevoicetranslater.genai, "Client", return_value=client) as client_factory,
            patch.object(livevoicetranslater.sd, "RawInputStream", return_value=input_stream) as input_factory,
            patch.object(livevoicetranslater.sd, "RawOutputStream", return_value=output_stream) as output_factory,
        ):
            with self.assertRaises(ExceptionGroup) as raised:
                await livevoicetranslater.run_translation("fr", 1, 2)

        self.assertIn("connection lost", str(raised.exception.exceptions[0]))
        self.assertEqual(client_factory.call_args.kwargs["http_options"].api_version, "v1beta")
        self.assertEqual(input_factory.call_args.kwargs["samplerate"], 16000)
        self.assertEqual(input_factory.call_args.kwargs["device"], 1)
        self.assertEqual(output_factory.call_args.kwargs["samplerate"], 24000)
        self.assertEqual(output_factory.call_args.kwargs["device"], 2)
        input_stream.__exit__.assert_called_once()
        output_stream.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()

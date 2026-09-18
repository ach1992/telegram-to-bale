from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import requests

from main import (
    BaleClient,
    Config,
    ConfigurationError,
    Forwarder,
    media_endpoint,
    split_text,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any | None = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self) -> Any:
        if isinstance(self._payload, ValueError):
            raise self._payload
        return self._payload


class ConfigTests(unittest.TestCase):
    def test_valid_config_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Config.from_environment(
                environ={
                    "API_ID": "12345",
                    "API_HASH": "hash",
                    "BALE_BOT_TOKEN": "token",
                    "BALE_CHAT_ID": "-1001",
                    "SOURCE_CHANNELS": " @one, @two, @one ",
                    "TG2BALE_DATA_DIR": directory,
                    "TG2BALE_WORKERS": "2",
                }
            )
        self.assertEqual(config.api_id, 12345)
        self.assertEqual(config.source_channels, ("@one", "@two"))
        self.assertEqual(config.workers, 2)

    def test_missing_required_value_fails(self) -> None:
        with self.assertRaises(ConfigurationError):
            Config.from_environment(environ={})

    def test_explicit_env_file_overrides_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "service.env"
            env_file.write_text(
                "API_ID=12345\n"
                "API_HASH=file-hash\n"
                "BALE_BOT_TOKEN=file-token\n"
                "BALE_CHAT_ID=file-chat\n"
                "SOURCE_CHANNELS=@file-channel\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "API_ID": "99999",
                    "API_HASH": "process-hash",
                    "BALE_BOT_TOKEN": "process-token",
                    "BALE_CHAT_ID": "process-chat",
                    "SOURCE_CHANNELS": "@process-channel",
                },
                clear=True,
            ):
                config = Config.from_environment(env_file=env_file)

        self.assertEqual(config.api_id, 12345)
        self.assertEqual(config.api_hash, "file-hash")
        self.assertEqual(config.source_channels, ("@file-channel",))

    def test_numeric_channels_are_converted_to_integers(self) -> None:
        values = {
            "API_ID": "12345",
            "API_HASH": "hash",
            "BALE_BOT_TOKEN": "token",
            "BALE_CHAT_ID": "chat",
            "SOURCE_CHANNELS": "-100123,@name,-100123",
        }
        config = Config.from_environment(environ=values)
        self.assertEqual(config.source_channels, (-100123, "@name"))

    def test_invalid_worker_count_fails(self) -> None:
        values = {
            "API_ID": "12345",
            "API_HASH": "hash",
            "BALE_BOT_TOKEN": "token",
            "BALE_CHAT_ID": "chat",
            "SOURCE_CHANNELS": "@one",
            "TG2BALE_WORKERS": "100",
        }
        with self.assertRaises(ConfigurationError):
            Config.from_environment(environ=values)


class TextTests(unittest.TestCase):
    def test_split_text_preserves_content(self) -> None:
        text = "alpha beta gamma\ndelta epsilon zeta"
        chunks = split_text(text, 12)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 12 for chunk in chunks))

    def test_empty_text_produces_no_chunks(self) -> None:
        self.assertEqual(split_text("", 100), [])


class MediaTests(unittest.TestCase):
    def test_media_endpoint(self) -> None:
        self.assertEqual(media_endpoint(Path("photo.jpg")), ("sendPhoto", "photo"))
        self.assertEqual(media_endpoint(Path("clip.bin"), "video/mp4"), ("sendVideo", "video"))
        self.assertEqual(media_endpoint(Path("archive.zip")), ("sendDocument", "document"))


class BaleClientTests(unittest.TestCase):
    @staticmethod
    def config() -> Config:
        return Config(
            api_id=1,
            api_hash="hash",
            bale_bot_token="token",
            bale_chat_id="chat",
            source_channels=("@source",),
            data_dir=Path("/tmp/tg2bale-tests"),
            max_retries=3,
            retry_base_seconds=0.25,
        )

    def test_retries_retryable_http_status(self) -> None:
        responses = [
            FakeResponse(500, {"ok": False}, "failed"),
            FakeResponse(200, {"ok": True}, "ok"),
        ]
        delays: list[float] = []

        def request(*args: Any, **kwargs: Any) -> FakeResponse:
            return responses.pop(0)

        client = BaleClient(self.config(), request=request, sleeper=delays.append)
        self.assertTrue(client.send_text("hello"))
        self.assertEqual(delays, [0.25])

    def test_does_not_retry_permanent_http_error(self) -> None:
        calls = 0

        def request(*args: Any, **kwargs: Any) -> FakeResponse:
            nonlocal calls
            calls += 1
            return FakeResponse(400, {"ok": False}, "bad request")

        client = BaleClient(self.config(), request=request, sleeper=lambda _: None)
        self.assertFalse(client.send_text("hello"))
        self.assertEqual(calls, 1)

    def test_media_stream_is_reopened_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.bin"
            path.write_bytes(b"complete-file")
            received: list[bytes] = []

            def request(*args: Any, **kwargs: Any) -> FakeResponse:
                files = kwargs["files"]
                stream = files["document"][1]
                received.append(stream.read())
                if len(received) == 1:
                    return FakeResponse(500, {"ok": False}, "retry")
                return FakeResponse(200, {"ok": True}, "ok")

            client = BaleClient(self.config(), request=request, sleeper=lambda _: None)
            self.assertTrue(client.send_media(path))
            self.assertEqual(received, [b"complete-file", b"complete-file"])

    def test_request_errors_redact_bot_token(self) -> None:
        client = BaleClient(self.config())
        error = requests.Timeout(f"timeout for {client.base_url}/sendMessage")
        rendered = client._safe_request_error(error)
        self.assertNotIn("token", rendered)
        self.assertIn("<bale-api>", rendered)

    def test_retry_after_header_is_used(self) -> None:
        responses = [
            FakeResponse(429, {"ok": False}, "rate limited", {"Retry-After": "7"}),
            FakeResponse(200, {"ok": True}, "ok"),
        ]
        delays: list[float] = []

        def request(*args: Any, **kwargs: Any) -> FakeResponse:
            return responses.pop(0)

        client = BaleClient(self.config(), request=request, sleeper=delays.append)
        self.assertTrue(client.send_text("hello"))
        self.assertEqual(delays, [7.0])

    def test_network_errors_are_retried(self) -> None:
        calls = 0

        def request(*args: Any, **kwargs: Any) -> FakeResponse:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise requests.Timeout("timeout")
            return FakeResponse(200, {"ok": True}, "ok")

        client = BaleClient(self.config(), request=request, sleeper=lambda _: None)
        self.assertTrue(client.send_text("hello"))
        self.assertEqual(calls, 2)


class ForwarderTests(unittest.IsolatedAsyncioTestCase):
    async def test_web_preview_message_forwards_text_without_downloading(self) -> None:
        class Message:
            id = 9
            message = "https://example.com"
            media = object()
            photo = None
            video = None
            document = None

        class Telegram:
            async def download_media(self, message: Any, file: str) -> str:
                raise AssertionError("download_media must not be called")

        class Bale:
            def __init__(self) -> None:
                self.texts: list[str] = []

            def send_text(self, text: str) -> bool:
                self.texts.append(text)
                return True

        with tempfile.TemporaryDirectory() as directory:
            config = Config(
                api_id=1,
                api_hash="hash",
                bale_bot_token="token",
                bale_chat_id="chat",
                source_channels=("@source",),
                data_dir=Path(directory),
            )
            bale = Bale()
            forwarder = Forwarder(Telegram(), config, bale)  # type: ignore[arg-type]
            await forwarder._process_message(Message())

        self.assertEqual(bale.texts, ["https://example.com"])

    async def test_media_retries_without_caption_before_fallback(self) -> None:
        class FileInfo:
            name = "clip.mp4"
            mime_type = "video/mp4"

        class Message:
            id = 7
            chat_id = -1001
            message = "caption"
            media = object()
            photo = None
            video = object()
            document = object()
            file = FileInfo()

        class Telegram:
            async def download_media(self, message: Any, file: str) -> str:
                Path(file).write_bytes(b"video")
                return file

        class Bale:
            def __init__(self) -> None:
                self.captions: list[str] = []
                self.texts: list[str] = []

            def send_media(self, path: Path, caption: str, mime_type: str | None) -> bool:
                self.captions.append(caption)
                return caption == ""

            def send_text(self, text: str) -> bool:
                self.texts.append(text)
                return True

        with tempfile.TemporaryDirectory() as directory:
            config = Config(
                api_id=1,
                api_hash="hash",
                bale_bot_token="token",
                bale_chat_id="chat",
                source_channels=("@source",),
                data_dir=Path(directory),
            )
            config.temp_dir.mkdir(parents=True)
            bale = Bale()
            forwarder = Forwarder(Telegram(), config, bale)  # type: ignore[arg-type]
            await forwarder._process_message(Message())

        self.assertEqual(bale.captions, ["caption", ""])
        self.assertEqual(bale.texts, ["caption"])


if __name__ == "__main__":
    unittest.main()

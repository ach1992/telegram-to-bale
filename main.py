#!/usr/bin/env python3
"""Forward messages from Telegram channels to a Bale channel."""

from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

import requests
from dotenv import load_dotenv

try:
    from telethon import TelegramClient, events
except ImportError:  # pragma: no cover - reported clearly at runtime
    TelegramClient = None  # type: ignore[assignment]
    events = None  # type: ignore[assignment]

LOGGER = logging.getLogger("tg2bale")
PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_DIR / "data"
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bale_bot_token: str
    bale_chat_id: str
    source_channels: tuple[str | int, ...]
    data_dir: Path
    request_timeout: float = 120.0
    max_retries: int = 3
    retry_base_seconds: float = 1.0
    workers: int = 1
    queue_size: int = 100
    text_limit: int = 4096

    @property
    def session_path(self) -> Path:
        return self.data_dir / "telegram"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    @classmethod
    def from_environment(
        cls,
        env_file: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "Config":
        if env_file is not None:
            if not env_file.is_file():
                raise ConfigurationError(f"Environment file not found: {env_file}")
            load_dotenv(dotenv_path=env_file, override=True)
        elif (PROJECT_DIR / ".env").is_file():
            load_dotenv(dotenv_path=PROJECT_DIR / ".env", override=False)

        values = os.environ if environ is None else environ

        api_id_raw = _required(values, "API_ID")
        try:
            api_id = int(api_id_raw)
        except ValueError as exc:
            raise ConfigurationError("API_ID must be a positive integer") from exc
        if api_id <= 0:
            raise ConfigurationError("API_ID must be a positive integer")

        channels = _parse_channels(_required(values, "SOURCE_CHANNELS"))
        data_dir = Path(values.get("TG2BALE_DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser()

        return cls(
            api_id=api_id,
            api_hash=_required(values, "API_HASH"),
            bale_bot_token=_required(values, "BALE_BOT_TOKEN"),
            bale_chat_id=_required(values, "BALE_CHAT_ID"),
            source_channels=channels,
            data_dir=data_dir.resolve(),
            request_timeout=_positive_float(values, "TG2BALE_REQUEST_TIMEOUT", 120.0),
            max_retries=_bounded_int(values, "TG2BALE_MAX_RETRIES", 3, 1, 10),
            retry_base_seconds=_positive_float(values, "TG2BALE_RETRY_BASE_SECONDS", 1.0),
            workers=_bounded_int(values, "TG2BALE_WORKERS", 1, 1, 8),
            queue_size=_bounded_int(values, "TG2BALE_QUEUE_SIZE", 100, 1, 10000),
            text_limit=_bounded_int(values, "TG2BALE_TEXT_LIMIT", 4096, 256, 100000),
        )


def _required(values: Mapping[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ConfigurationError(f"Missing required setting: {key}")
    return value


def _positive_float(values: Mapping[str, str], key: str, default: float) -> float:
    raw = values.get(key, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be a number") from exc
    if value <= 0:
        raise ConfigurationError(f"{key} must be greater than zero")
    return value


def _bounded_int(
    values: Mapping[str, str], key: str, default: int, minimum: int, maximum: int
) -> int:
    raw = values.get(key, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{key} must be between {minimum} and {maximum}")
    return value


def _parse_channels(raw: str) -> tuple[str | int, ...]:
    channels: list[str | int] = []
    seen: set[str] = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        channel: str | int = int(value) if value.lstrip("-").isdigit() else value
        identity = str(channel)
        if identity not in seen:
            channels.append(channel)
            seen.add(identity)
    if not channels:
        raise ConfigurationError("SOURCE_CHANNELS must contain at least one channel")
    return tuple(channels)


def split_text(text: str, limit: int) -> list[str]:
    """Split text without dropping characters and prefer natural boundaries."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if not text:
        return []

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at < 1:
            split_at = limit
        else:
            split_at += 1
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(remaining)
    return chunks


def media_endpoint(path: Path, mime_type: str | None = None) -> tuple[str, str]:
    suffix = path.suffix.lower()
    mime = (mime_type or mimetypes.guess_type(path.name)[0] or "").lower()
    if suffix in PHOTO_EXTENSIONS or mime in {"image/jpeg", "image/png", "image/webp"}:
        return "sendPhoto", "photo"
    if suffix in VIDEO_EXTENSIONS or mime.startswith("video/"):
        return "sendVideo", "video"
    return "sendDocument", "document"


class BaleClient:
    def __init__(
        self,
        config: Config,
        request: Callable[..., requests.Response] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = f"https://tapi.bale.ai/bot{config.bale_bot_token}"
        self.chat_id = config.bale_chat_id
        self.timeout = (10.0, config.request_timeout)
        self.max_retries = config.max_retries
        self.retry_base_seconds = config.retry_base_seconds
        self.text_limit = config.text_limit
        self._request_override = request
        self._thread_local = threading.local()
        self._sleep = sleeper

    def _post(self, *args: Any, **kwargs: Any) -> requests.Response:
        if self._request_override is not None:
            return self._request_override(*args, **kwargs)
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": "telegram-to-bale/2.0.0"})
            self._thread_local.session = session
        return session.post(*args, **kwargs)

    def send_text(self, text: str) -> bool:
        chunks = split_text(text, self.text_limit)
        if not chunks:
            return True
        for index, chunk in enumerate(chunks, start=1):
            if not self._send_text_chunk(chunk):
                LOGGER.error("Failed to send text chunk %s/%s", index, len(chunks))
                return False
        return True

    def _send_text_chunk(self, text: str) -> bool:
        def perform() -> requests.Response:
            return self._post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=self.timeout,
            )

        return self._perform_with_retry("sendMessage", perform)

    def send_media(
        self, path: Path, caption: str = "", mime_type: str | None = None
    ) -> bool:
        endpoint, field_name = media_endpoint(path, mime_type)

        def perform() -> requests.Response:
            with path.open("rb") as stream:
                content_type = (
                    mime_type
                    or mimetypes.guess_type(path.name)[0]
                    or "application/octet-stream"
                )
                files = {field_name: (path.name, stream, content_type)}
                data = {"chat_id": self.chat_id}
                if caption:
                    data["caption"] = caption
                return self._post(
                    f"{self.base_url}/{endpoint}",
                    data=data,
                    files=files,
                    timeout=self.timeout,
                )

        return self._perform_with_retry(endpoint, perform)

    def _perform_with_retry(
        self, endpoint: str, perform: Callable[[], requests.Response]
    ) -> bool:
        for attempt in range(1, self.max_retries + 1):
            response: requests.Response | None = None
            try:
                response = perform()
                if self._is_success(response):
                    LOGGER.info("Bale %s succeeded", endpoint)
                    return True

                body = _response_excerpt(response)
                LOGGER.warning(
                    "Bale %s failed on attempt %s/%s: HTTP %s, response=%s",
                    endpoint,
                    attempt,
                    self.max_retries,
                    response.status_code,
                    body,
                )
                if (
                    response.status_code not in RETRYABLE_STATUS_CODES
                    and _retry_after_seconds(response) is None
                ):
                    return False
            except requests.RequestException as exc:
                LOGGER.warning(
                    "Bale %s network error on attempt %s/%s: %s",
                    endpoint,
                    attempt,
                    self.max_retries,
                    self._safe_request_error(exc),
                )
            except OSError as exc:
                LOGGER.error("Cannot read media for %s: %s", endpoint, exc)
                return False

            if attempt < self.max_retries:
                delay = self._retry_delay(attempt, response)
                LOGGER.info("Retrying Bale %s in %.1f seconds", endpoint, delay)
                self._sleep(delay)

        return False

    def _safe_request_error(self, exc: requests.RequestException) -> str:
        message = str(exc).replace(self.base_url, "<bale-api>")
        return message or exc.__class__.__name__

    @staticmethod
    def _is_success(response: requests.Response) -> bool:
        if not 200 <= response.status_code < 300:
            return False
        try:
            payload = response.json()
        except ValueError:
            return True
        return not isinstance(payload, dict) or payload.get("ok", True) is not False

    def _retry_delay(self, attempt: int, response: requests.Response | None) -> float:
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            return min(max(retry_after, 0.0), 300.0)
        return min(self.retry_base_seconds * (2 ** (attempt - 1)), 30.0)


class Forwarder:
    def __init__(self, client: TelegramClient, config: Config, bale: BaleClient) -> None:
        self.client = client
        self.config = config
        self.bale = bale
        self.queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=config.queue_size)
        self.worker_tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.config.temp_dir.mkdir(parents=True, exist_ok=True)
        for index in range(self.config.workers):
            task = asyncio.create_task(
                self._worker(index + 1), name=f"forwarder-{index + 1}"
            )
            self.worker_tasks.append(task)

    async def stop(self) -> None:
        await self.queue.join()
        for task in self.worker_tasks:
            task.cancel()
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()

    async def on_message(self, event: Any) -> None:
        if self.queue.full():
            LOGGER.warning("Forward queue is full; waiting for capacity")
        await self.queue.put(event.message)
        LOGGER.debug("Queued Telegram message %s", getattr(event.message, "id", "unknown"))

    async def _worker(self, worker_id: int) -> None:
        LOGGER.info("Forward worker %s started", worker_id)
        while True:
            message = await self.queue.get()
            try:
                await self._process_message(message)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Unhandled error while forwarding a Telegram message")
            finally:
                self.queue.task_done()

    async def _process_message(self, message: Any) -> None:
        text = getattr(message, "message", None) or ""
        media = getattr(message, "media", None)
        downloadable_media = bool(
            getattr(message, "photo", None)
            or getattr(message, "video", None)
            or getattr(message, "document", None)
        )

        if not media or not downloadable_media:
            if text:
                success = await asyncio.to_thread(self.bale.send_text, text)
                if not success:
                    LOGGER.error("Text message %s was not delivered", message.id)
            elif media:
                LOGGER.info(
                    "Skipping unsupported Telegram media type for message %s",
                    getattr(message, "id", "unknown"),
                )
            return

        mime_type = _message_mime_type(message)
        suffix = _message_suffix(message, mime_type)
        chat_id = getattr(message, "chat_id", "unknown")
        filename = f"{chat_id}_{message.id}_{uuid4().hex[:8]}{suffix}"
        target = self.config.temp_dir / filename
        downloaded: Path | None = None

        try:
            downloaded_path = await self._download_with_retry(message, target)
            if not downloaded_path:
                raise RuntimeError("Telegram returned no downloaded file path")
            downloaded = Path(downloaded_path)
            if not downloaded.is_file():
                raise RuntimeError(f"Downloaded file does not exist: {downloaded}")

            success = await asyncio.to_thread(
                self.bale.send_media, downloaded, text, mime_type
            )
            if not success and text:
                LOGGER.info("Retrying media without caption for message %s", message.id)
                success = await asyncio.to_thread(
                    self.bale.send_media, downloaded, "", mime_type
                )
                if success:
                    await asyncio.to_thread(self.bale.send_text, text)
            if not success:
                await self._send_fallback(downloaded, text, mime_type)
        finally:
            for path in {target, downloaded}:
                if path is not None:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError as exc:
                        LOGGER.warning("Could not remove temporary file %s: %s", path, exc)

    async def _download_with_retry(self, message: Any, target: Path) -> str | None:
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return await self.client.download_media(message, file=str(target))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                target.unlink(missing_ok=True)
                LOGGER.warning(
                    "Telegram download failed on attempt %s/%s for message %s: %s",
                    attempt,
                    self.config.max_retries,
                    getattr(message, "id", "unknown"),
                    exc.__class__.__name__,
                )
                if attempt < self.config.max_retries:
                    delay = min(
                        self.config.retry_base_seconds * (2 ** (attempt - 1)), 30.0
                    )
                    await asyncio.sleep(delay)
        return None

    async def _send_fallback(self, path: Path, caption: str, mime_type: str | None) -> None:
        endpoint, _ = media_endpoint(path, mime_type)
        if endpoint == "sendVideo":
            preview = path.with_suffix(path.suffix + ".jpg")
            try:
                created = await asyncio.to_thread(generate_video_preview, path, preview)
                if created:
                    fallback_caption = _append_marker(caption, "#video_failed")
                    sent = await asyncio.to_thread(
                        self.bale.send_media, preview, fallback_caption, "image/jpeg"
                    )
                    if sent:
                        return
            finally:
                preview.unlink(missing_ok=True)

        marker = "#image_failed" if endpoint == "sendPhoto" else "#file_failed"
        fallback_text = _append_marker(caption, marker)
        await asyncio.to_thread(self.bale.send_text, fallback_text)


def _response_excerpt(response: requests.Response) -> str:
    try:
        text = response.text
    except Exception:
        return "<unavailable>"
    return text.replace("\n", " ")[:500]


def _retry_after_seconds(response: requests.Response | None) -> float | None:
    if response is None:
        return None
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    parameters = payload.get("parameters")
    if isinstance(parameters, dict):
        value = parameters.get("retry_after")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _message_mime_type(message: Any) -> str | None:
    file_info = getattr(message, "file", None)
    mime_type = getattr(file_info, "mime_type", None)
    return str(mime_type) if mime_type else None


def _message_suffix(message: Any, mime_type: str | None) -> str:
    if getattr(message, "photo", None):
        return ".jpg"
    file_info = getattr(message, "file", None)
    original_name = getattr(file_info, "name", None)
    if original_name:
        suffix = Path(str(original_name)).suffix
        if suffix and len(suffix) <= 16:
            return suffix.lower()
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed and len(guessed) <= 16:
        return guessed
    return ".bin"


def _append_marker(text: str, marker: str) -> str:
    return f"{text}\n{marker}".strip()


def generate_video_preview(source: Path, destination: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                "1",
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-y",
                str(destination),
            ],
            check=False,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOGGER.warning("Could not generate video preview: %s", exc)
        return False
    return result.returncode == 0 and destination.is_file()


def configure_logging() -> None:
    level_name = os.getenv("TG2BALE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run_bot(config: Config) -> None:
    if TelegramClient is None or events is None:
        raise RuntimeError(
            "Telethon is not installed. Install requirements.txt in the virtual environment."
        )
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.temp_dir.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(config.session_path), config.api_id, config.api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError(
            "Telegram session is not authorized. Run authenticate.py before starting the service."
        )

    forwarder = Forwarder(client, config, BaleClient(config))
    await forwarder.start()
    client.add_event_handler(
        forwarder.on_message,
        events.NewMessage(chats=list(config.source_channels)),
    )

    LOGGER.info(
        "Bot started; monitoring %s channel(s) with %s worker(s)",
        len(config.source_channels),
        config.workers,
    )
    try:
        await client.run_until_disconnected()
    finally:
        await forwarder.stop()
        if client.is_connected():
            await client.disconnect()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(os.environ["TG2BALE_ENV_FILE"])
        if os.getenv("TG2BALE_ENV_FILE")
        else None,
        help="Path to an environment file",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration and exit without connecting",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    try:
        config = Config.from_environment(args.env_file)
        if args.check_config:
            print(
                "Configuration is valid: "
                f"channels={len(config.source_channels)}, data_dir={config.data_dir}"
            )
            return 0
        asyncio.run(run_bot(config))
        return 0
    except (ConfigurationError, RuntimeError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        LOGGER.info("Stopped by user")
        return 130
    except Exception:
        LOGGER.exception("Fatal error")
        return 1


if __name__ == "__main__":
    sys.exit(main())

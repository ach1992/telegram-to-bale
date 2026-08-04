#!/usr/bin/env python3
"""Create or validate the Telegram session used by the service."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

try:
    from telethon import TelegramClient
except ImportError:  # pragma: no cover - reported clearly at runtime
    TelegramClient = None  # type: ignore[assignment]

PROJECT_DIR = Path(__file__).resolve().parent


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--phone", help="Telegram phone number in international format")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the existing session is authorized",
    )
    return parser.parse_args(argv)


def load_telegram_settings(env_file: Path | None) -> tuple[int, str, Path]:
    if env_file is not None:
        if not env_file.is_file():
            raise ValueError(f"Environment file not found: {env_file}")
        load_dotenv(env_file, override=True)
    elif (PROJECT_DIR / ".env").is_file():
        load_dotenv(PROJECT_DIR / ".env", override=False)

    raw_api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    if not raw_api_id or not api_hash:
        raise ValueError("API_ID and API_HASH are required")
    try:
        api_id = int(raw_api_id)
    except ValueError as exc:
        raise ValueError("API_ID must be a positive integer") from exc
    if api_id <= 0:
        raise ValueError("API_ID must be a positive integer")

    data_dir = Path(
        os.getenv("TG2BALE_DATA_DIR", str(PROJECT_DIR / "data"))
    ).expanduser().resolve()
    return api_id, api_hash, data_dir


async def authenticate(
    api_id: int,
    api_hash: str,
    data_dir: Path,
    phone: str | None,
    check: bool,
) -> int:
    if TelegramClient is None:
        raise ValueError("Telethon is not installed. Install requirements.txt first.")
    data_dir.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(str(data_dir / "telegram"), api_id, api_hash)
    await client.connect()
    try:
        if await client.is_user_authorized():
            print("Telegram session is authorized.")
            return 0
        if check:
            print("Telegram session is not authorized.", file=sys.stderr)
            return 1
        await client.start(phone=phone)
        if not await client.is_user_authorized():
            print("Telegram authorization did not complete.", file=sys.stderr)
            return 1
        print("Telegram session created successfully.")
        return 0
    finally:
        await client.disconnect()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        api_id, api_hash, data_dir = load_telegram_settings(args.env_file)
        return asyncio.run(
            authenticate(api_id, api_hash, data_dir, args.phone, args.check)
        )
    except (OSError, ValueError) as exc:
        print(f"Authentication error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Authentication cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

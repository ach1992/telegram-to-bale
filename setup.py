#!/usr/bin/env python3
"""Create a local .env file for development use."""

from __future__ import annotations

import getpass
import os
from pathlib import Path


def prompt(label: str, secret: bool = False) -> str:
    while True:
        value = (getpass.getpass(label) if secret else input(label)).strip()
        if value:
            return value
        print("A value is required.")


def main() -> int:
    print("Telegram-to-Bale local configuration")
    api_id = prompt("Telegram API ID: ")
    if not api_id.isdigit() or int(api_id) <= 0:
        print("API ID must be a positive integer.")
        return 1

    api_hash = prompt("Telegram API Hash: ", secret=True)
    bale_token = prompt("Bale Bot Token: ", secret=True)
    bale_chat_id = prompt("Bale Channel Chat ID: ")
    channels = prompt("Telegram channels, comma-separated: ")

    env_path = Path(__file__).resolve().parent / ".env"
    env_path.write_text(
        "\n".join(
            [
                f"API_ID={api_id}",
                f"API_HASH={api_hash}",
                f"BALE_BOT_TOKEN={bale_token}",
                f"BALE_CHAT_ID={bale_chat_id}",
                f"SOURCE_CHANNELS={channels}",
                f"TG2BALE_DATA_DIR={env_path.parent / 'data'}",
                "TG2BALE_REQUEST_TIMEOUT=120",
                "TG2BALE_MAX_RETRIES=3",
                "TG2BALE_RETRY_BASE_SECONDS=1",
                "TG2BALE_WORKERS=1",
                "TG2BALE_QUEUE_SIZE=100",
                "TG2BALE_TEXT_LIMIT=4096",
                "TG2BALE_LOG_LEVEL=INFO",
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(env_path, 0o600)
    print(f"Configuration written to {env_path}")
    print("Next run: python authenticate.py")
    print("Then run: python main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

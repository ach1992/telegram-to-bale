#!/usr/bin/env python3
"""Administrative CLI for the Telegram-to-Bale service."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Sequence

SERVICE_NAME = "tg2bale.service"
APP_DIR = Path("/opt/telegram-to-bale")
ENV_FILE = Path("/etc/telegram-to-bale.env")
DATA_DIR = Path("/var/lib/tg2bale")
PYTHON = APP_DIR / ".venv/bin/python"
VERSION_FILE = APP_DIR / "VERSION"


def run(command: Sequence[str]) -> int:
    try:
        return subprocess.run(list(command), check=False).returncode
    except FileNotFoundError:
        print(f"Command not found: {command[0]}", file=sys.stderr)
        return 127


def require_root() -> bool:
    if os.geteuid() == 0:
        return True
    print("This command requires root. Run it with sudo.", file=sys.stderr)
    return False


def service_command(action: str) -> int:
    if action != "status" and not require_root():
        return 1
    return run(["systemctl", action, SERVICE_NAME])


def show_logs(lines: int, follow: bool) -> int:
    command = ["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager"]
    if follow:
        command.extend(["--follow"])
    return run(command)


def doctor() -> int:
    checks: list[tuple[str, bool, str]] = []
    checks.append(
        ("systemctl", shutil.which("systemctl") is not None, "systemctl is available")
    )
    checks.append(("ffmpeg", shutil.which("ffmpeg") is not None, "ffmpeg is available"))
    checks.append(
        ("application", (APP_DIR / "main.py").is_file(), f"{APP_DIR}/main.py exists")
    )
    checks.append(("python", PYTHON.is_file(), f"{PYTHON} exists"))
    checks.append(("environment", ENV_FILE.is_file(), f"{ENV_FILE} exists"))
    checks.append(("data directory", DATA_DIR.is_dir(), f"{DATA_DIR} exists"))

    if ENV_FILE.is_file():
        mode = stat.S_IMODE(ENV_FILE.stat().st_mode)
        checks.append(
            ("environment permissions", mode & 0o007 == 0, f"mode is {mode:04o}")
        )

    failed = False
    for name, ok, detail in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
        failed = failed or not ok

    if PYTHON.is_file() and (APP_DIR / "main.py").is_file() and ENV_FILE.is_file():
        config_rc = run(
            [
                str(PYTHON),
                str(APP_DIR / "main.py"),
                "--env-file",
                str(ENV_FILE),
                "--check-config",
            ]
        )
        print(f"[{'OK' if config_rc == 0 else 'FAIL'}] configuration validation")
        failed = failed or config_rc != 0

        session_rc = run(
            [
                str(PYTHON),
                str(APP_DIR / "authenticate.py"),
                "--env-file",
                str(ENV_FILE),
                "--check",
            ]
        )
        print(f"[{'OK' if session_rc == 0 else 'FAIL'}] Telegram session authorization")
        failed = failed or session_rc != 0

    active_rc = run(["systemctl", "is-active", "--quiet", SERVICE_NAME])
    print(f"[{'OK' if active_rc == 0 else 'FAIL'}] service active")
    failed = failed or active_rc != 0
    return 1 if failed else 0


def uninstall(purge: bool, assume_yes: bool) -> int:
    if not require_root():
        return 1
    script = APP_DIR / "uninstall.sh"
    if not script.is_file():
        print(f"Uninstaller not found: {script}", file=sys.stderr)
        return 1
    command = ["bash", str(script)]
    if purge:
        command.append("--purge")
    if assume_yes:
        command.append("--yes")
    return run(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    version = (
        VERSION_FILE.read_text(encoding="utf-8").strip()
        if VERSION_FILE.is_file()
        else "development"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {version}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("status", "start", "stop", "restart"):
        subparsers.add_parser(command, help=f"Run systemctl {command} for {SERVICE_NAME}")

    logs = subparsers.add_parser("logs", help="Show service logs")
    logs.add_argument("-n", "--lines", type=int, default=100)
    logs.add_argument("-f", "--follow", action="store_true")

    subparsers.add_parser(
        "doctor", help="Validate installation, config, session, and service"
    )

    remove = subparsers.add_parser("uninstall", help="Remove the installed application")
    remove.add_argument(
        "--purge", action="store_true", help="Also delete config, session, and service user"
    )
    remove.add_argument("--yes", action="store_true", help="Do not ask for confirmation")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"status", "start", "stop", "restart"}:
        return service_command(args.command)
    if args.command == "logs":
        if args.lines < 1:
            parser.error("--lines must be positive")
        return show_logs(args.lines, args.follow)
    if args.command == "doctor":
        return doctor()
    if args.command == "uninstall":
        return uninstall(args.purge, args.yes)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())

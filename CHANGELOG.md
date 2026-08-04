# Changelog

## 2.0.0 - 2026-08-04

### Added

- Debian 12/13 and Ubuntu 22.04/24.04/26.04 CI matrix.
- Dedicated unprivileged `tg2bale` service user and hardened systemd unit.
- Bounded forwarding queue, configurable workers, timeouts, exponential backoff, and rate-limit retry support.
- Long-text splitting, deterministic media classification, and safe temporary-file handling.
- `authenticate.py` for explicit Telegram session creation and validation.
- `teltobale logs` and `teltobale doctor` commands.
- Installer rollback, legacy config/session migration, non-interactive mode, and safe uninstall modes.
- Unit and shell smoke tests.

### Changed

- Production application path is now `/opt/telegram-to-bale`.
- Production configuration is stored in `/etc/telegram-to-bale.env`.
- Telegram session and temporary media are stored in `/var/lib/tg2bale`.
- Python dependencies are installed only in an isolated virtual environment.
- Minimum supported Python version is 3.10.

### Fixed

- Missing `python3-venv` package on minimal Debian/Ubuntu installations.
- Incorrect use of `pip --break-system-packages` inside a virtual environment.
- Blocking HTTP requests inside the Telethon event handler.
- Missing HTTP timeouts and incomplete retry behavior.
- Media retry attempts reusing an exhausted file stream.
- Relative paths that depended on the service working directory.
- Root service execution and overly broad filesystem access.
- Unsafe repeated installation and incomplete uninstall behavior.

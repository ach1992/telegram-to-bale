<p align="center"><a href="./README.fa.md">فارسی</a></p>

# Telegram to Bale Forwarder

A production-oriented Python service that monitors selected Telegram channels through a user session and forwards text, photos, videos, and documents to a Bale channel through the Bale Bot API.

## Highlights

- Text, photo, video, and document forwarding
- Non-blocking Telegram event handling with a bounded worker queue
- HTTP connect/read timeouts, exponential backoff, and retry handling for transient failures and rate limits
- Text splitting for long messages
- Video preview fallback through `ffmpeg`
- Secure, isolated systemd service running as the dedicated `tg2bale` user
- Idempotent installer with legacy config/session migration and rollback
- Persistent config under `/etc` and session/media state under `/var/lib`
- CLI for status, logs, restart, diagnostics, and safe uninstall
- CI coverage across supported Debian and Ubuntu releases

## Supported systems

The installer supports systemd-based servers running:

- Debian 12 or newer
- Ubuntu 22.04 LTS or newer
- Python 3.10 or newer

The CI matrix currently covers Debian 12/13 and Ubuntu 22.04/24.04/26.04.

## Requirements

You need:

- Telegram `API_ID` and `API_HASH` from `my.telegram.org`
- A Telegram phone number that can access every source channel
- A Bale bot token
- The Bale destination channel chat ID
- The Bale bot added to the destination channel with sufficient permissions

## Quick installation

Run the bootstrap installer as root while preserving an interactive terminal:

```bash
sudo bash -c 'bash <(curl -fsSL https://raw.githubusercontent.com/ach1992/telegram-to-bale/main/install.sh)'
```

The installer will:

1. Verify the operating system.
2. Install `python3`, `python3-venv`, `ffmpeg`, and other required packages.
3. Install the application under `/opt/telegram-to-bale`.
4. Create a dedicated `tg2bale` system user.
5. Store secrets in `/etc/telegram-to-bale.env` with restricted permissions.
6. Create the Telegram session under `/var/lib/tg2bale`.
7. Install and start `tg2bale.service`.
8. Install the global `teltobale` command.

Re-running the same installer updates the application while preserving the existing configuration and authorized Telegram session. Older installations that used a project-local `.env` and `session.session` are migrated when their systemd unit can be detected.

### Non-interactive installation

Initial configuration can be supplied through environment variables. A Telegram session still requires interactive authentication unless `--skip-auth` is used.

```bash
sudo env \
  API_ID='12345' \
  API_HASH='replace-me' \
  BALE_BOT_TOKEN='replace-me' \
  BALE_CHAT_ID='replace-me' \
  SOURCE_CHANNELS='@channel_one,@channel_two' \
  bash -c 'bash <(curl -fsSL https://raw.githubusercontent.com/ach1992/telegram-to-bale/main/install.sh) --non-interactive --skip-auth'
```

Authenticate later with:

```bash
sudo -u tg2bale /opt/telegram-to-bale/.venv/bin/python \
  /opt/telegram-to-bale/authenticate.py \
  --env-file /etc/telegram-to-bale.env
sudo systemctl restart tg2bale.service
```

## Management CLI

```bash
teltobale status
sudo teltobale start
sudo teltobale stop
sudo teltobale restart
teltobale logs -n 200
teltobale logs --follow
sudo teltobale doctor
```

Direct systemd commands also work:

```bash
sudo systemctl status tg2bale.service
sudo journalctl -u tg2bale.service -n 100 --no-pager
```

## Configuration

The production environment file is `/etc/telegram-to-bale.env`.

| Variable | Required | Default | Description |
|---|---:|---:|---|
| `API_ID` | Yes | - | Telegram application ID |
| `API_HASH` | Yes | - | Telegram application hash |
| `BALE_BOT_TOKEN` | Yes | - | Bale bot token |
| `BALE_CHAT_ID` | Yes | - | Bale destination chat/channel ID |
| `SOURCE_CHANNELS` | Yes | - | Comma-separated Telegram usernames or IDs |
| `TG2BALE_DATA_DIR` | No | `/var/lib/tg2bale` in production | Session and temporary media directory |
| `TG2BALE_REQUEST_TIMEOUT` | No | `120` | Bale HTTP read timeout in seconds |
| `TG2BALE_MAX_RETRIES` | No | `3` | Maximum send attempts, between 1 and 10 |
| `TG2BALE_RETRY_BASE_SECONDS` | No | `1` | Base exponential-backoff delay |
| `TG2BALE_WORKERS` | No | `1` | Queue workers, between 1 and 8; `1` preserves global order |
| `TG2BALE_QUEUE_SIZE` | No | `100` | Maximum queued Telegram messages |
| `TG2BALE_TEXT_LIMIT` | No | `4096` | Text chunk size sent to Bale |
| `TG2BALE_LOG_LEVEL` | No | `INFO` | Python logging level |

After editing the config:

```bash
sudo chmod 0640 /etc/telegram-to-bale.env
sudo chown root:tg2bale /etc/telegram-to-bale.env
sudo teltobale doctor
sudo teltobale restart
```

## Local development

```bash
git clone https://github.com/ach1992/telegram-to-bale.git
cd telegram-to-bale
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python setup.py
.venv/bin/python authenticate.py
.venv/bin/python main.py
```

Run tests:

```bash
python3 -m compileall -q main.py authenticate.py cli.py setup.py tests
python3 -m unittest discover -s tests -v
bash tests/test_scripts.sh
```

## Uninstall

Preserve config and session data for a later reinstall:

```bash
sudo teltobale uninstall
```

Delete the application, configuration, session, and service user permanently:

```bash
sudo teltobale uninstall --purge
```

## Troubleshooting

Run the diagnostic command first:

```bash
sudo teltobale doctor
```

Then inspect logs:

```bash
teltobale logs -n 200
```

Common causes include an unauthorized Telegram session, inaccessible source channels, an invalid Bale token/chat ID, missing Bale channel permissions, network filtering, rate limits, or media rejected by the destination API.

## Security notes

- The service does not run as root.
- Secrets are stored outside the application directory and should remain mode `0640`, owned by `root:tg2bale`.
- The systemd unit uses filesystem, privilege, namespace, kernel, and capability restrictions.
- Temporary media and Telegram session files are stored under `/var/lib/tg2bale`, not in the repository.
- Never commit `.env` or `.session` files.

## License

MIT License, Copyright 2025-2026 ach1992.

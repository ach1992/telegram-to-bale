<p align="center">
 <a href="./README.fa.md">
 فارسی
 </a>
</p>

# 🤖 Telegram to Bale Forwarder Bot

A fully automated Python bot that listens to specific Telegram channels and forwards all messages (text, photos, videos, and documents) to your **Bale messenger** channel using the Bale Bot API.

---

## 🚀 Features

- ✅ Forward **text messages**
- 🖼 Forward **images** via Bale's `sendPhoto`
- 📹 Forward **videos** via Bale's `sendVideo`
- 📄 Forward **documents** as-is
- 🔁 Retry sending files up to 3 times on failure
- 🖼 Generate preview image for failed video uploads using `ffmpeg`
- ⚙️ Automatically detects file type and selects correct Bale API method
- 📡 systemd service integration for auto-start
- 🧰 Command-line control tool (`teltobale`)

---

## 🔑 What You’ll Need

To use this bot, you’ll need a few keys and IDs. Here’s what they are and how to get them:

| Name | Description | How to Get It |
|------|-------------|---------------|
| **API ID** | Your Telegram app's API ID | Create a Telegram app at [my.telegram.org](https://my.telegram.org/auth) and you’ll receive an API ID. |
| **API Hash** | Your Telegram app's secret hash | Comes with the API ID above on Telegram's developer portal. |
| **Phone Number** | Your phone number used to log in to Telegram | Enter it in international format (e.g., +989123456789). |
| **Bale Bot Token** | Token for your bot on Bale Messenger | Create a bot at [tapi.bale.ai](https://tapi.bale.ai), and get your bot token (starts with `bot...`). |
| **Bale Channel's Chat ID** | Numeric ID of your **Bale channel** | Add the bot as an admin, send a message in your Bale channel, then call: `https://tapi.bale.ai/bot<YourToken>/getUpdates` and copy the numeric `chat_id`. |
| **Telegram Channels** | Telegram channel usernames to monitor | Example: `@newsch1,@mediahub2` (you must be a member). |

> ⚠️ Be sure to add your Bale bot as **admin** in your Bale channel.

---

## 📦 Requirements

- Python 3.7+
- Debian/Ubuntu Linux (recommended)
- `ffmpeg` installed
- Internet access (for both Telegram and Bale)

---

## ⚙️ Quick Install

Just run this single line:

```
bash <(curl -Ls https://raw.githubusercontent.com/ach1992/telegram-to-bale/main/install.sh)
```

## This will:

- Clone the project
- Install all dependencies
- Ask for your Telegram/Bale credentials
- Create a Telegram session
- Create and run systemd service
- Register teltobale CLI tool

---

## 🔁 Running the Bot

After install, the bot will run in the background automatically.
To check or control the bot:

```
sudo systemctl status tg2bale.service
sudo systemctl restart tg2bale.service
```

---

## 💻 CLI Tool: teltobale
A global command is created:

```
teltobale status     # Check bot status
teltobale restart    # Restart the bot
teltobale stop       # Stop the bot
teltobale uninstall  # Uninstall the bot
```

---

## 🧪 Developer Setup

```
git clone https://github.com/ach1992/telegram-to-bale.git
cd telegram-to-bale
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup.py
```

---

## 🧼 Uninstall

```
teltobale uninstall
```

---

## 📁 Project Structure

```
├── main.py               # Bot logic
├── cli.py                # CLI tool
├── setup.py              # Setup wizard
├── setup.sh              # Full auto installer
├── install.sh            # Curl-based bootstrap
├── uninstall.sh          # Full cleanup
├── requirements.txt
├── .env                  # Credentials file (auto-generated)
├── temp/                 # Temp folder for media
```

---

## ❗ Troubleshooting

### Media not sending?
- Ensure proper file extensions, and that ffmpeg is installed.

### 401/403 errors from Bale?
- Your bot may not be added to the channel as admin, or token is wrong.

### Telegram login fails?
- Make sure your server is not blocked by Telegram.

---

## 📃 License

MIT License © 2025 ach1992

---

## ⭐ Star History

[![Stargazers over time](https://starchart.cc/ach1992/telegram-to-bale.svg)](https://starchart.cc/ach1992/telegram-to-bale)

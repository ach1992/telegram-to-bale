# 📲 Telegram to Bale Forwarder

A lightweight Python script that forwards messages from **public Telegram channels** to a **Bale channel** using Bale Bot API.

---

## 🚀 Features

- 📡 Monitors multiple public Telegram channels
- 📤 Sends messages to your Bale bot/channel in real-time
- 🔐 Uses `.env` file for sensitive data (created automatically)
- ✅ Fully automated setup with one-liner installer

---

## 🔧 Requirements

- Python 3.6+
- A Telegram account (to create `api_id` / `api_hash`)
- A Bale bot token (created via `@BotFatherBale`)
- Your Bale channel's `chat_id`
- Public Telegram channel usernames (e.g. `@bbc`, `@channel1`)

---

## ⚙️ Installation (One-Liner)

```bash
bash <(curl -Ls https://raw.githubusercontent.com/ach1992/telegram-to-bale/main/install.sh)

---

## ✅ This will:

Install required Python dependencies
Ask you for Telegram & Bale info
Generate .env file with your config
Start listening for new Telegram messages and forward them to Bale

---

## 📝 Example .env File (Auto-generated)

API_ID=123456
API_HASH=your_telegram_api_hash
BALE_BOT_TOKEN=your_bale_bot_token
BALE_CHAT_ID=123456789
SOURCE_CHANNELS=@channel1,@channel2

---

## 📁 Project Structure

telegram-to-bale/
├── main.py         # Main script to forward messages
├── setup.py        # Optional setup script (used by install.sh)
├── install.sh      # One-liner installer script
├── requirements.txt
├── .gitignore
├── README.md
└── README.fa.md    # 📄 Persian guide

---

## 🛡️ Security

🔐 Your API keys and tokens are stored only in .env
.env is excluded from Git using .gitignore
Do NOT upload .env to GitHub or share it with others

---

## 📄 License

This project is released under the MIT License.
Feel free to use, modify, and distribute it.

---

## ⭐ Star History

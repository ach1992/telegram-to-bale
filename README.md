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

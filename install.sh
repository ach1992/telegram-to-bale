#!/bin/bash

echo "📦 Telegram to Bale - Installer"
echo "-------------------------------"

# نصب پیش‌نیازها
echo "🔧 Installing dependencies..."
apt update -y && apt install python3 python3-pip git curl -y

# کلون کردن پروژه (اگر خودشون نخواستن با git نصب کنن)
# git clone https://github.com/ach1992/telegram-to-bale.git

# نصب کتابخانه‌های پایتون
pip3 install telethon requests python-dotenv

# گرفتن اطلاعات از کاربر
read -p "👉 Enter your Telegram API ID: " api_id
read -p "👉 Enter your Telegram API Hash: " api_hash
read -p "👉 Enter your Bale Bot Token: " bale_token
read -p "👉 Enter your Bale Channel Chat ID: " chat_id
read -p "👉 Enter Telegram Channels (comma-separated): " channels

# ساخت فایل .env
cat > .env <<EOF
API_ID=$api_id
API_HASH=$api_hash
BALE_BOT_TOKEN=$bale_token
BALE_CHAT_ID=$chat_id
SOURCE_CHANNELS=$channels
EOF

echo "✅ .env file created."
echo "🚀 Running the bot now..."

# اجرای فایل اصلی
python3 main.py

#!/bin/bash

echo "📦 Setting up Telegram-to-Bale Bot"
echo "----------------------------------"

# نصب پکیج‌های مورد نیاز
apt update -y && apt install python3 python3-pip git curl ffmpeg -y

# ساخت محیط مجازی پایتون
python3 -m venv .venv
source .venv/bin/activate

# نصب کتابخانه‌ها در محیط مجازی
pip install --break-system-packages telethon requests python-dotenv pillow

# دریافت اطلاعات از کاربر
read -p "👉 Enter your Telegram API ID: " api_id
read -p "👉 Enter your Telegram API Hash: " api_hash
read -p "👉 Enter your Telegram Phone Number (with +98 or +1): " phone
read -p "👉 Enter your Bale Bot Token: " bale_token
read -p "👉 Enter your Bale Channel Chat ID: " chat_id
read -p "👉 Enter Telegram Channels (comma-separated): " channels

# ذخیره در فایل .env
cat > .env <<EOF
API_ID=$api_id
API_HASH=$api_hash
BALE_BOT_TOKEN=$bale_token
BALE_CHAT_ID=$chat_id
SOURCE_CHANNELS=$channels
EOF

echo "✅ .env file created."

# ساخت فایل session
echo "🔐 Logging into Telegram to create session..."
python3 -c "
from telethon.sync import TelegramClient
client = TelegramClient('session', $api_id, '$api_hash')
client.start(phone='$phone')
print('✅ Session created successfully!')
"

# ساخت سرویس systemd
echo "🛠 Setting up systemd service..."

cat > /etc/systemd/system/tg2bale.service <<EOF
[Unit]
Description=Telegram to Bale Forwarder
After=network.target

[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/python $(pwd)/main.py
Restart=on-failure
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tg2bale.service
systemctl restart tg2bale.service

echo "✅ Service installed and started: tg2bale.service"

# نصب CLI به عنوان teltobale
echo "⚙️ Installing 'teltobale' CLI command..."

cat > /usr/local/bin/teltobale <<EOF
#!/bin/bash
$(pwd)/.venv/bin/python $(pwd)/cli.py "\$@"
EOF

chmod +x /usr/local/bin/teltobale

echo "✅ You can now use 'teltobale' anywhere:"
echo "   - teltobale status"
echo "   - teltobale restart"
echo "   - teltobale uninstall"

#!/bin/bash

echo "📦 Installing Telegram-to-Bale Bot with isolated Python environment"
echo "--------------------------------------------------------------------"

# Install system packages
apt update -y && apt install python3 python3-pip python3-venv git curl ffmpeg -y

# Create virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Installing Python packages in an isolated environment
pip install --upgrade pip
pip install telethon requests python-dotenv pillow

# Get information from the user
read -p "👉 Enter your Telegram API ID: " api_id
read -p "👉 Enter your Telegram API Hash: " api_hash
read -p "👉 Enter your Bale Bot Token: " bale_token
read -p "👉 Enter your Bale Channel Chat ID: " chat_id
read -p "👉 Enter Telegram Channels (comma-separated): " channels

# Create .env file
cat > .env <<EOF
API_ID=$api_id
API_HASH=$api_hash
BALE_BOT_TOKEN=$bale_token
BALE_CHAT_ID=$chat_id
SOURCE_CHANNELS=$channels
EOF

echo "✅ .env file created."

# Create systemd service
echo "🛠 Setting up systemd service..."

cat > /etc/systemd/system/tg2bale.service <<EOF
[Unit]
Description=Telegram to Bale Forwarder
After=network.target

[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/python main.py
Restart=on-failure
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

# Service activation
systemctl daemon-reload
systemctl enable tg2bale.service
systemctl start tg2bale.service

echo "✅ Service installed and started: tg2bale.service"

# Install CLI tool called teltobale
echo "⚙️ Installing 'teltobale' CLI command..."

CLI_PATH="$(realpath ./cli.py)"
cat > /usr/local/bin/teltobale <<EOF
#!/bin/bash
$(pwd)/.venv/bin/python $CLI_PATH "\$@"
EOF

chmod +x /usr/local/bin/teltobale

echo "✅ You can now use 'teltobale' anywhere:"
echo "   - teltobale status"
echo "   - teltobale restart"
echo "   - teltobale uninstall"

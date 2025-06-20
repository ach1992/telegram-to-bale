#!/bin/bash

echo "🗑️ Uninstalling Telegram-to-Bale Bot"
echo "------------------------------------"

# متوقف کردن سرویس
echo "🛑 Stopping and disabling systemd service..."
systemctl stop tg2bale.service 2>/dev/null
systemctl disable tg2bale.service 2>/dev/null
rm -f /etc/systemd/system/tg2bale.service
systemctl daemon-reload

# حذف فایل‌های مربوط به پروژه
echo "🧹 Removing project files (.env, session, temp)..."
rm -f .env
rm -rf session*
rm -rf temp/

# حذف CLI از سیستم
echo "🗑️ Removing 'teltobale' CLI command..."
rm -f /usr/local/bin/teltobale

echo "✅ Uninstall complete."
echo "📌 You may delete the remaining project folder manually if needed."

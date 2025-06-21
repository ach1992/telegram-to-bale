#!/bin/bash

echo "🚀 Cloning Telegram-to-Bale repository..."
git clone https://github.com/ach1992/telegram-to-bale.git

cd telegram-to-bale || {
  echo "❌ Failed to enter project directory."
  exit 1
}

echo "📦 Running inner installer..."
bash setup.sh

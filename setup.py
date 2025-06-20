print("🔧 Welcome to Telegram-to-Bale Setup Wizard\n")

api_id = input("Enter your Telegram API ID: ").strip()
api_hash = input("Enter your Telegram API Hash: ").strip()
bale_token = input("Enter your Bale Bot Token: ").strip()
bale_chat_id = input("Enter your Bale Channel Chat ID: ").strip()
channels = input("Enter Telegram Channel usernames separated by comma (e.g., @ch1,@ch2): ").strip()

with open(".env", "w") as f:
    f.write(f"API_ID={api_id}\n")
    f.write(f"API_HASH={api_hash}\n")
    f.write(f"BALE_BOT_TOKEN={bale_token}\n")
    f.write(f"BALE_CHAT_ID={bale_chat_id}\n")
    f.write(f"SOURCE_CHANNELS={channels}\n")

print("\n✅ .env file created successfully!")
print("👉 Now run: python3 main.py")

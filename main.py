from telethon import TelegramClient, events
from dotenv import load_dotenv
import os
import requests
import asyncio

# بارگذاری تنظیمات از .env
load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bale_bot_token = os.getenv("BALE_BOT_TOKEN")
bale_chat_id = os.getenv("BALE_CHAT_ID")
source_channels = os.getenv("SOURCE_CHANNELS").split(',')

client = TelegramClient('session', api_id, api_hash)

BALE_API = f"https://tapi.bale.ai/bot{bale_bot_token}"

# ارسال متن به بله
def send_text_to_bale(text):
    payload = {
        "chat_id": bale_chat_id,
        "text": text
    }
    r = requests.post(f"{BALE_API}/sendMessage", json=payload)
    print(f"[Text] Sent: {r.status_code} – {text[:40]}...")

# ارسال فایل (عکس، ویدیو، PDF و...) به بله
def send_file_to_bale(file_path):
    file_name = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        files = {
            'document': (file_name, f)
        }
        data = {
            'chat_id': bale_chat_id
        }
        r = requests.post(f"{BALE_API}/sendDocument", data=data, files=files)
        print(f"[File] Sent: {r.status_code} – {file_name}")
    os.remove(file_path)

@client.on(events.NewMessage(chats=source_channels))
async def handler(event):
    message = event.message

    # اگر پیام فقط متن باشد
    if message.text and not message.media:
        send_text_to_bale(message.text)
        return

    # اگر پیام مدیا (عکس/فایل/ویدیو) داشته باشد
    try:
        file_path = f"temp/{message.id}"
        os.makedirs("temp", exist_ok=True)
        await client.download_media(message, file_path)
        if os.path.exists(file_path):
            send_file_to_bale(file_path)
    except Exception as e:
        print(f"⚠️ Error downloading/sending file: {e}")

client.start()
print("🤖 Bot is running. Waiting for messages...")
client.run_until_disconnected()

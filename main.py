from telethon import TelegramClient, events
from dotenv import load_dotenv
import os
import requests
import asyncio
import subprocess

# Load environment variables
load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bale_bot_token = os.getenv("BALE_BOT_TOKEN")
bale_chat_id = os.getenv("BALE_CHAT_ID")
source_channels = os.getenv("SOURCE_CHANNELS").split(',')

client = TelegramClient('session', api_id, api_hash)
BALE_API = f"https://tapi.bale.ai/bot{bale_bot_token}"

os.makedirs("temp", exist_ok=True)

def send_text_to_bale(text):
    payload = {
        "chat_id": bale_chat_id,
        "text": text
    }
    try:
        r = requests.post(f"{BALE_API}/sendMessage", json=payload)
        if r.status_code == 200:
            print(f"[✅ Text] Sent: {text[:40]}...")
        else:
            print(f"[❌ Text] Failed: {r.status_code}")
    except Exception as e:
        print(f"[⚠️ Text Error] {e}")

def send_fallback_preview(image_path, caption):
    with open(image_path, 'rb') as f:
        files = {'photo': ('preview.jpg', f)}
        data = {
            'chat_id': bale_chat_id,
            'caption': caption
        }
        try:
            r = requests.post(f"{BALE_API}/sendPhoto", data=data, files=files)
            print(f"[📷 Fallback Preview] Status: {r.status_code}")
        except Exception as e:
            print(f"[❌ Preview Error] {e}")

def send_file_to_bale(file_path, caption=None):
    file_name = os.path.basename(file_path)
    ext = os.path.splitext(file_name)[-1].lower()
    success = False

    for attempt in range(3):
        try:
            with open(file_path, 'rb') as f:
                files = {'document': (file_name, f)}
                data = {'chat_id': bale_chat_id}
                if caption:
                    data['caption'] = caption
                r = requests.post(f"{BALE_API}/sendDocument", data=data, files=files)
                if r.status_code == 200:
                    print(f"[✅ File] Sent: {file_name}")
                    success = True
                    break
                else:
                    print(f"[❌ File] Attempt {attempt+1} failed: {r.status_code}")
        except Exception as e:
            print(f"[⚠️ File Error] Attempt {attempt+1}: {e}")

    if not success:
        preview_path = f"{file_path}.jpg"
        if ext in [".mp4", ".mov", ".mkv"]:
            subprocess.run([
                "ffmpeg", "-i", file_path, "-ss", "00:00:01.000", "-vframes", "1", preview_path,
                "-y", "-loglevel", "error"
            ])
            caption_fallback = (caption or "") + "\n#video_failed"
            if os.path.exists(preview_path):
                send_fallback_preview(preview_path, caption_fallback)
                os.remove(preview_path)
        elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
            caption_fallback = (caption or "") + "\n#image_failed"
            send_text_to_bale(caption_fallback)
    os.remove(file_path)

@client.on(events.NewMessage(chats=source_channels))
async def handler(event):
    message = event.message
    caption = message.text or ""

    if message.text and not message.media:
        send_text_to_bale(message.text)
        return

    try:
        file_path = f"temp/{message.id}"
        await client.download_media(message, file_path)
        if os.path.exists(file_path):
            send_file_to_bale(file_path, caption)
    except Exception as e:
        print(f"[❌ Download/Send Error] {e}")

client.start()
print("🤖 Bot is running. Listening for messages...")
client.run_until_disconnected()

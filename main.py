from telethon import TelegramClient, events
from dotenv import load_dotenv
import os
import requests

# Load settings from .env
load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bale_bot_token = os.getenv("BALE_BOT_TOKEN")
bale_chat_id = os.getenv("BALE_CHAT_ID")
source_channels = os.getenv("SOURCE_CHANNELS").split(',')

client = TelegramClient('session', api_id, api_hash)

@client.on(events.NewMessage(chats=source_channels))
async def handler(event):
    message = event.message.message
    send_to_bale(message)

def send_to_bale(text):
    url = f"https://tapi.bale.ai/bot{bale_bot_token}/sendMessage"
    payload = {
        "chat_id": bale_chat_id,
        "text": text
    }
    r = requests.post(url, json=payload)
    print(f"📤 Sent to Bale: {r.status_code} – {text[:50]}...")

client.start()
client.run_until_disconnected()

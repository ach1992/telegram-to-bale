import os
import asyncio
import logging
import requests
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "").split(',')
BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg2bale")

client = TelegramClient('session', API_ID, API_HASH)


async def send_text_to_bale(text: str):
    url = f"https://tapi.bale.ai/bot{BALE_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": BALE_CHAT_ID,
        "text": text
    }

    for attempt in range(3):
        try:
            response = requests.post(url, data=data)
            if response.ok:
                logger.info("✅ Text sent to Bale")
                return True
            else:
                logger.warning(f"⚠️ Bale text error: {response.text}")
        except Exception as e:
            logger.error(f"❌ Text send error: {e}")
        await asyncio.sleep(2)
    return False


async def send_media_to_bale(media_path: str, caption: str = ""):
    file_ext = os.path.splitext(media_path)[1].lower()
    if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
        method = 'sendPhoto'
        file_field = 'photo'
    elif file_ext in ['.mp4', '.mov', '.avi', '.mkv']:
        method = 'sendVideo'
        file_field = 'video'
    else:
        logger.warning(f"❌ Unsupported media type: {file_ext}")
        return False

    url = f"https://tapi.bale.ai/bot{BALE_BOT_TOKEN}/{method}"
    data = {
        "chat_id": BALE_CHAT_ID,
        "caption": caption
    }

    for attempt in range(3):
        try:
            with open(media_path, 'rb') as f:
                files = {file_field: f}
                response = requests.post(url, data=data, files=files)
                if response.ok:
                    logger.info("✅ Media sent to Bale")
                    return True
                else:
                    logger.warning(f"⚠️ Bale media error: {response.text}")
        except Exception as e:
            logger.error(f"❌ Media send error: {e}")
        await asyncio.sleep(2)
    return False


@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    logger.info("📥 New message received")
    msg = event.message
    text = msg.text or ""
    media_path = None

    if msg.media:
        try:
            media_path = await msg.download_media(file="temp")
            sent = await send_media_to_bale(media_path, caption=text)
            if not sent:
                await send_text_to_bale("[❌ Failed to send media] " + (text or ""))
            os.remove(media_path)
        except Exception as e:
            logger.error(f"❌ Media handling error: {e}")
            await send_text_to_bale("[❌ Error downloading media] " + (text or ""))
    else:
        await send_text_to_bale(text)


if __name__ == '__main__':
    logger.info("🚀 Starting Telegram client")
    client.start()
    client.run_until_disconnected()

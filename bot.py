import logging
import traceback
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from datetime import datetime

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,  # Mengubah level menjadi DEBUG agar bisa melihat log lebih banyak
    handlers=[
        logging.FileHandler("bot_errors.log"),
        logging.StreamHandler()
    ]
)

API_ID = 29386534  # Ganti dengan API ID kamu
API_HASH = "8f35dec4c4de801ec648cf4ca1cf04e9"
BOT_TOKEN = "7766823813:AAHOtLoVip5vxtKbwly1kt3JTX7FwN1Ko_M"
LOG_CHANNEL = -1001234567890  # Ganti dengan ID channel log

bot = Client("digital_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Fungsi untuk mengirim log error ke admin channel
async def send_error_log(message: str):
    await bot.send_message(LOG_CHANNEL, message)

# Fungsi untuk menangani error yang tidak terduga
async def handle_error(client, message, error):
    error_message = f"Terjadi kesalahan: {str(error)}"
    # Menyimpan traceback ke dalam log file
    logging.error(f"{error_message}\n{traceback.format_exc()}")
    # Mengirimkan error ke channel log
    await send_error_log(f"Error terjadi pada {datetime.now()}\nUser: {message.from_user.id if message else 'Unknown'}\nPesan: {message.text if message else 'No message'}\n{error_message}")

# Menangani FloodWait secara manual
async def handle_flood_wait(exception: FloodWait):
    await send_error_log(f"FloodWait exception occurred at {datetime.now()}\nException: {exception}")
    logging.error(f"FloodWait occurred at {datetime.now()}\n{traceback.format_exc()}")

# Handler untuk pesan dan callback query
@bot.on_message(filters.command("start"))
async def start(client, message):
    try:
        logging.debug("Start command received")  # Log untuk debugging
        # Tempatkan kode bot kamu di sini
        pass
    except FloodWait as e:
        await handle_flood_wait(e)
    except Exception as e:
        await handle_error(client, message, e)

@bot.on_callback_query()
async def callback_handler(client, callback_query):
    try:
        logging.debug("Callback query received")  # Log untuk debugging
        # Tempatkan kode callback kamu di sini
        pass
    except FloodWait as e:
        await handle_flood_wait(e)
    except Exception as e:
        await handle_error(client, callback_query.message, e)

# Menjalankan bot
logging.debug("Bot is starting...")
bot.run()
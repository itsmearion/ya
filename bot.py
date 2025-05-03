import logging
import traceback
from pyrogram import Client
from pyrogram.errors import FloodWait
from datetime import datetime

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.ERROR,
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
    
# Menangkap error pada callback query atau pesan yang masuk
@bot.on_message()
async def error_handler(client, message):
    try:
        # Tempatkan kode bot di sini
        pass  # Ganti dengan logika bot yang kamu implementasikan
    except Exception as e:
        await handle_error(client, message, e)

@bot.on_callback_query()
async def callback_error_handler(client, callback_query):
    try:
        # Tempatkan kode callback yang kamu implementasikan
        pass  # Ganti dengan logika callback yang kamu implementasikan
    except Exception as e:
        await handle_error(client, callback_query.message, e)

# Menangani FloodWait (misalnya bot dibatasi untuk mengirim pesan)
@bot.on_exception(FloodWait)
async def handle_flood_wait(client, exception):
    await send_error_log(f"FloodWait exception occurred at {datetime.now()}\nException: {exception}")
    logging.error(f"FloodWait occurred at {datetime.now()}\n{traceback.format_exc()}")

# Menjalankan bot
bot.run()
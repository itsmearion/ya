#!/usr/bin/env python
# Bot Telegram untuk memblokir user yang keluar dari channel
# Menggunakan python-telegram-bot

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ganti dengan token bot Anda dari BotFather
BOT_TOKEN = "7659666747:AAHyfrRHzJg2GuyaN3f-RZs94ABHr4rPFXo"

# Simpan daftar channel yang dimonitor
monitored_channels = set(testerbott4)

# Menyimpan username admin untuk verifikasi
admin_username = "m4thewn"

# Command /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Selamat datang di Leave Blocker Bot! Bot ini akan memblokir user yang keluar dari channel Anda.\n\n"
        "Perintah yang tersedia:\n"
        "/setadmin [username] - Mengatur admin bot\n"
        "/monitor [channel_id] - Mulai memantau channel\n"
        "/unmonitor [channel_id] - Berhenti memantau channel\n"
        "/list - Menampilkan daftar channel yang dipantau"
    )

# Fungsi untuk verifikasi admin
def is_admin(update: Update) -> bool:
    global admin_username
    
    if not admin_username:
        update.message.reply_text("Admin belum diatur. Gunakan /setadmin [username] terlebih dahulu.")
        return False
    
    sender = update.message.from_user.username
    if sender != admin_username:
        update.message.reply_text("Hanya admin yang bisa menggunakan perintah ini.")
        return False
    
    return True

# Command /setadmin
async def set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global admin_username
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Gunakan format: /setadmin [username]")
        return
    
    admin_username = context.args[0].replace("@", "")
    await update.message.reply_text(f"Admin bot diatur ke: @{admin_username}")

# Command /monitor
async def monitor_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Gunakan format: /monitor [channel_id]")
        return
    
    channel_id = context.args[0]
    
    try:
        # Verifikasi bot adalah admin di channel
        chat_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=context.bot.id)
        
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Bot harus menjadi admin di channel dengan izin memblokir user")
            return
        
        monitored_channels.add(channel_id)
        await update.message.reply_text(f"Channel {channel_id} sekarang dipantau. Bot akan memblokir user yang keluar.")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}. Pastikan bot sudah dimasukkan ke channel dan menjadi admin.")

# Command /unmonitor
async def unmonitor_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Gunakan format: /unmonitor [channel_id]")
        return
    
    channel_id = context.args[0]
    
    if channel_id in monitored_channels:
        monitored_channels.remove(channel_id)
        await update.message.reply_text(f"Channel {channel_id} tidak lagi dipantau.")
    else:
        await update.message.reply_text(f"Channel {channel_id} tidak ada dalam daftar pantauan.")

# Command /list
async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    
    if not monitored_channels:
        await update.message.reply_text("Tidak ada channel yang dipantau saat ini.")
        return
    
    message = "Channel yang sedang dipantau:\n"
    for channel in monitored_channels:
        message += f"- {channel}\n"
    
    await update.message.reply_text(message)

# Menangani event saat user keluar dari channel
async def handle_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    
    # Cek apakah channel ada dalam daftar pantauan
    if chat_id in monitored_channels:
        user = update.message.left_chat_member
        
        # Jika yang keluar bukan bot itu sendiri
        if user.id != context.bot.id:
            try:
                # Blokir user yang keluar
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=user.id)
                
                # Kirim notifikasi
                username = user.username or user.id
                await update.effective_chat.send_message(f"User @{username} telah keluar dari channel dan diblokir.")
            except Exception as e:
                await update.effective_chat.send_message(f"Gagal memblokir user: {str(e)}")

def main() -> None:
    # Buat aplikasi
    application = Application.builder().token(BOT_TOKEN).build()

    # Tambahkan handler untuk commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setadmin", set_admin))
    application.add_handler(CommandHandler("monitor", monitor_channel))
    application.add_handler(CommandHandler("unmonitor", unmonitor_channel))
    application.add_handler(CommandHandler("list", list_channels))
    
    # Tambahkan handler untuk event user keluar
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_chat_member))

    # Mulai bot
    logger.info("Bot telah dimulai")
    application.run_polling()

if __name__ == "__main__":
    main()
from telethon import TelegramClient, events, version
from telethon.tl.functions.channels import EditBannedRequest, GetParticipantRequest
from telethon.tl.types import ChatBannedRights, PeerUser, PeerChannel, ChannelParticipantBanned
from telethon.errors import UserAdminInvalidError, ChatAdminRequiredError, AuthKeyError, UserNotParticipantError
import asyncio
import logging
import time
import sys
import os

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("autoban.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ganti dengan API ID & HASH dari https://my.telegram.org
api_id = api_id = 29386534
api_hash = '8f35dec4c4de801ec648cf4ca1cf04e9'

# Konfigurasi channel yang ingin dipantau
# PENTING: Untuk channel public, gunakan username TANPA '@' 
# Untuk channel private, gunakan ID numerik dengan format '-100' di depan
MONITORED_CHANNELS = [
    'testerbott4',           # Channel publik (tanpa @)
    -1001234567890,      # Channel private (gunakan angka, bukan string)
]

# Daftar ID admin yang akan menerima laporan
ADMINS = [6467919046]  # Ganti dengan ID Telegram Anda

# Pesan yang akan dikirim ke admin
BAN_MESSAGE = """⚠️ *PENGGUNA DIBANNED* ⚠️

User {user_mention} telah keluar dari channel dan otomatis dibanned.

📝 *Detail:*
• *User ID:* `{user_id}`
• *Waktu:* `{time}`
• *Channel:* `{channel_title}`

✅ *Status:* Dibanned permanen"""

# Inisialisasi client dengan parameter tambahan untuk menangani error UPDATE_APP_TO_LOGIN
client = TelegramClient(
    'userbot_autoban', 
    api_id, 
    api_hash,
    device_model="Termux Python",  
    system_version=f"Python {sys.version.split()[0]}",
    app_version=f"Telethon {version.__version__}"
)

# Hak blokir permanen
ban_rights = ChatBannedRights(
    until_date=None,  # Selamanya
    view_messages=True,
    send_messages=True,
    send_media=True,
    send_stickers=True,
    send_gifs=True,
    send_games=True,
    send_inline=True,
    embed_links=True
)

# Fungsi helper untuk memeriksa apakah channel dalam daftar yang dipantau
def is_monitored_channel(chat):
    """Memeriksa apakah chat/channel ada dalam daftar yang dipantau"""
    chat_id = chat.id
    chat_username = chat.username.lower() if chat.username else None
    
    for channel in MONITORED_CHANNELS:
        # Jika channel dalam bentuk string username (tanpa @)
        if isinstance(channel, str) and chat_username and channel.lower() == chat_username.lower():
            logger.info(f"✅ Channel {chat.title} (@{chat_username}) cocok dengan daftar pantauan")
            return True
        # Jika channel dalam bentuk integer ID
        elif isinstance(channel, int) and chat_id == channel:
            logger.info(f"✅ Channel {chat.title} (ID: {chat_id}) cocok dengan daftar pantauan")
            return True
    
    return False

@client.on(events.ChatAction)
async def autoban_handler(event):
    """Handler untuk event pengguna keluar channel"""
    # Cek apakah event adalah pengguna keluar
    if not (event.user_left or event.user_kicked):
        return
    
    try:
        # Ambil informasi chat dan user
        chat = await event.get_chat()
        user = await event.get_user()
        
        # Debug info
        logger.info(f"⚙️ Event terdeteksi: {'Pengguna keluar' if event.user_left else 'Pengguna dikeluarkan'}")
        logger.info(f"📌 Channel: {chat.title} ({chat.username or chat.id})")
        logger.info(f"👤 User: {user.first_name} ({user.id})")
        
        # Cek apakah channel dalam daftar yang dipantau
        if not is_monitored_channel(chat):
            logger.info(f"❌ Channel {chat.title} tidak dalam daftar pantauan. Mengabaikan event.")
            return
        
        # Jangan blokir diri sendiri
        me = await client.get_me()
        if user.id == me.id:
            logger.info(f"❌ Tidak akan memban diri sendiri")
            return
        
        # Dapatkan waktu untuk log dan pesan
        ban_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Cek apakah pengguna sudah dibanned sebelumnya
        try:
            participant = await client(GetParticipantRequest(chat, user))
            if isinstance(participant.participant, ChannelParticipantBanned):
                logger.info(f"ℹ️ Pengguna {user.first_name} sudah dibanned sebelumnya")
                return
        except UserNotParticipantError:
            logger.info(f"ℹ️ Pengguna {user.first_name} sudah tidak ada di channel")
            # Lanjutkan untuk ban
        except Exception as e:
            logger.error(f"❌ Error saat memeriksa status participant: {str(e)}")
        
        # Coba ban pengguna
        try:
            logger.info(f"🔄 Mencoba banned pengguna {user.first_name} (ID: {user.id})...")
            
            await client(EditBannedRequest(
                channel=chat,
                participant=user.id,
                banned_rights=ban_rights
            ))
            
            logger.info(f"✅ Berhasil banned pengguna {user.first_name} (ID: {user.id}) dari {chat.title}")
            
            # Buat mention pengguna untuk pesan
            user_mention = f"[{user.first_name}](tg://user?id={user.id})" if user.first_name else f"User {user.id}"
            
            # Siapkan pesan untuk admin dengan format yang lebih informatif
            ban_report = BAN_MESSAGE.format(
                user_mention=user_mention,
                user_id=user.id,
                time=ban_time,
                channel_title=chat.title
            )
            
            # Kirim laporan ke semua admin
            for admin_id in ADMINS:
                try:
                    await client.send_message(admin_id, ban_report, parse_mode='markdown')
                    logger.info(f"✅ Laporan banned berhasil dikirim ke admin {admin_id}")
                except Exception as e:
                    logger.error(f"❌ Gagal mengirim laporan ke admin {admin_id}: {str(e)}")
                    
        except UserAdminInvalidError:
            logger.warning(f"❌ Tidak dapat banned {user.first_name} (ID: {user.id}) karena mereka admin")
            
        except ChatAdminRequiredError:
            logger.error(f"❌ Tidak dapat banned {user.first_name} (ID: {user.id}) karena userbot bukan admin")
            
        except Exception as e:
            logger.error(f"❌ Gagal banned {user.first_name} (ID: {user.id}): {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error dalam handler: {str(e)}")

@client.on(events.NewMessage(pattern=r'\.status'))
async def status_handler(event):
    """Menampilkan status userbot ketika perintah .status dikirim"""
    if event.is_private:  # Hanya berfungsi di chat pribadi
        sender = await event.get_sender()
        if sender.id in ADMINS:
            await event.respond("✅ **Userbot AutoBan aktif dan berjalan!**\n"
                              f"📌 Memantau {len(MONITORED_CHANNELS)} channel\n"
                              f"👮 Admin terdaftar: {len(ADMINS)} orang\n\n"
                              f"ℹ️ Gunakan perintah `.cekban` untuk melihat pengguna yang dibanned")

@client.on(events.NewMessage(pattern=r'\.cekban'))
async def check_banned_handler(event):
    """Menampilkan daftar pengguna yang dibanned oleh userbot"""
    if event.is_private:  # Hanya berfungsi di chat pribadi
        sender = await event.get_sender()
        if sender.id in ADMINS:
            # Beri tahu admin perintah sedang berjalan
            processing_msg = await event.respond("⏳ **Sedang mengecek daftar banned users...**")
            
            try:
                banned_list = ""
                
                for channel_id in MONITORED_CHANNELS:
                    try:
                        # Dapatkan entity channel
                        if isinstance(channel_id, str):
                            channel = await client.get_entity(channel_id)
                        else:
                            channel = await client.get_entity(channel_id)
                        
                        banned_list += f"\n\n**Channel: {channel.title}**\n"
                        
                        # Ini adalah bagian dasar, tidak semua channel mengizinkan melihat banned list
                        banned_list += "_Proses pengecekan banned list memerlukan permission admin khusus_"
                        
                    except Exception as e:
                        banned_list += f"\nError checking {channel_id}: {str(e)}"
                
                # Update pesan dengan hasil
                await processing_msg.edit(f"📋 **Daftar Banned Users:**\n{banned_list}")
                
            except Exception as e:
                await processing_msg.edit(f"❌ **Error mendapatkan banned list:** {str(e)}")

async def check_permissions():
    """Memeriksa apakah userbot memiliki izin yang diperlukan di semua channel yang dipantau"""
    me = await client.get_me()
    logger.info(f"Userbot berjalan sebagai {me.first_name} (ID: {me.id})")
    
    for channel_id in MONITORED_CHANNELS:
        try:
            # Dapatkan entity channel
            if isinstance(channel_id, str):
                channel = await client.get_entity(channel_id)
            else:
                channel = await client.get_entity(channel_id)
                
            # Cek apakah userbot adalah admin
            participant = await client.get_permissions(channel, me.id)
            if participant.is_admin:
                logger.info(f"✅ Userbot adalah admin di {channel.title}")
                if participant.ban_users:
                    logger.info(f"✅ Userbot memiliki izin ban di {channel.title}")
                else:
                    logger.warning(f"⚠️ Userbot tidak memiliki izin ban di {channel.title}")
            else:
                logger.warning(f"⚠️ Userbot bukan admin di {channel.title}. Ban tidak akan berfungsi!")
                
        except Exception as e:
            logger.error(f"❌ Gagal memeriksa izin untuk {channel_id}: {str(e)}")

async def main():
    """Fungsi utama untuk menjalankan userbot"""
    try:
        # Tampilkan versi Telethon yang digunakan
        logger.info(f"Menggunakan Telethon versi {version.__version__}")
        
        # Coba memulai client dengan handling error yang lebih baik
        try:
            logger.info("Sedang memulai Telegram client...")
            await client.start()
            logger.info("Client berhasil dimulai!")
        except AuthKeyError as e:
            logger.critical(f"Error Autentikasi: {str(e)}")
            logger.critical("Coba update Telethon: pip install telethon --upgrade")
            return
        except Exception as e:
            logger.critical(f"Gagal memulai client: {str(e)}")
            return
        
        # Periksa izin saat startup
        await check_permissions()
        
        # Pesan konfirmasi bahwa userbot berjalan
        logger.info("====================================")
        logger.info("🤖 Calbin kontol dijalankan!")
        logger.info(f"🔍 Miel anj, babi, tai {len(MONITORED_CHANNELS)} channel")
        logger.info(f"👮 Laporan akan dikirim ke {len(ADMINS)} admin")
        logger.info("====================================")
        
        # Kirim notifikasi ke admin bahwa bot telah dimulai
        for admin_id in ADMINS:
            try:
                await client.send_message(admin_id, "🚀 **Userbot AutoBan telah diaktifkan!**\n\n"
                                          "Mulai sekarang pengguna yang keluar dari channel akan otomatis dibanned.\n"
                                          "Gunakan perintah `.status` untuk melihat status userbot.")
            except Exception as e:
                logger.error(f"Gagal mengirim notifikasi startup ke admin {admin_id}: {str(e)}")
        
        # Jalankan userbot sampai terputus
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        logger.info("Userbot dihentikan oleh pengguna")
    except Exception as e:
        logger.error(f"Error utama: {str(e)}")

# Jalankan program
if __name__ == "__main__":
    try:
        # Gunakan asyncio untuk menjalankan program utama
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program dihentikan oleh pengguna")
    except Exception as e:
        logger.error(f"Error saat menjalankan program: {str(e)}")
        sys.exit(1)
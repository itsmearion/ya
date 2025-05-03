from telethon import TelegramClient, events
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights, PeerUser, PeerChannel
from telethon.errors import UserAdminInvalidError, ChatAdminRequiredError
import asyncio
import logging
import time

# Konfigurasi logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Ganti dengan API ID & HASH dari https://my.telegram.org
api_id = 29386534
api_hash = '8f35dec4c4de801ec648cf4ca1cf04e9'

# Konfigurasi channel yang ingin dipantau
MONITORED_CHANNELS = ['@testerbott4']  # Gunakan username atau ID channel
ADMINS = [6467919046, 987654321]  # Daftar ID admin yang akan menerima laporan

# Pesan yang akan dikirim ke admin
BAN_MESSAGE = "⚠️ OTOMATIS BANNED ⚠️\nPengguna {user_mention} ({user_id}) telah keluar dari channel dan otomatis dibanned."

client = TelegramClient('userbot_autoban', api_id, api_hash)

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

@client.on(events.ChatAction)
async def autoban_handler(event):
    # Cek apakah event adalah pengguna keluar
    if not (event.user_left or event.user_kicked):
        return
    
    try:
        # Ambil informasi chat dan user
        chat = await event.get_chat()
        user = await event.get_user()
        
        # Verifikasi chat adalah channel yang dipantau
        chat_identifier = '@' + chat.username if chat.username else str(chat.id)
        if chat_identifier not in MONITORED_CHANNELS:
            return
        
        # Jangan blokir diri sendiri
        me = await client.get_me()
        if user.id == me.id:
            return
        
        # Dapatkan waktu saat ini untuk log
        ban_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Ban pengguna
        try:
            await client(EditBannedRequest(
                channel=chat,
                participant=user.id,
                banned_rights=ban_rights
            ))
            
            logger.info(f"✅ [{ban_time}] Berhasil banned pengguna {user.first_name} (ID: {user.id}) dari {chat.title}")
            
            # Buat mention pengguna
            user_mention = f"[{user.first_name}](tg://user?id={user.id})" if user.first_name else f"User {user.id}"
            
            # Siapkan pesan untuk admin
            ban_report = BAN_MESSAGE.format(user_mention=user_mention, user_id=user.id)
            
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

async def check_permissions():
    """Memeriksa apakah userbot memiliki izin yang diperlukan di semua channel yang dipantau"""
    me = await client.get_me()
    logger.info(f"Userbot berjalan sebagai {me.first_name} (ID: {me.id})")
    
    for channel_id in MONITORED_CHANNELS:
        try:
            # Hapus @ jika ada di depan username
            if channel_id.startswith('@'):
                channel = await client.get_entity(channel_id)
            else:
                channel = await client.get_entity(int(channel_id))
                
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

@client.on(events.NewMessage(pattern=r'\.status'))
async def status_handler(event):
    """Menampilkan status userbot ketika perintah .status dikirim"""
    if event.is_private:  # Hanya berfungsi di chat pribadi
        sender = await event.get_sender()
        if sender.id in ADMINS:
            await event.respond("✅ **Userbot AutoBan aktif dan berjalan!**\n"
                              f"Memantau channel: {', '.join(MONITORED_CHANNELS)}\n"
                              f"Admin yang dilaporkan: {len(ADMINS)} orang")

async def main():
    await client.start()
    
    # Periksa izin saat startup
    await check_permissions()
    
    # Pesan konfirmasi bahwa userbot berjalan
    logger.info("====================================")
    logger.info("🤖 Userbot AutoBan berhasil dijalankan!")
    logger.info(f"🔍 Memantau {len(MONITORED_CHANNELS)} channel")
    logger.info(f"👮 Laporan akan dikirim ke {len(ADMINS)} admin")
    logger.info("====================================")
    
    # Jalankan userbot sampai terputus
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
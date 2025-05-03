import asyncio
import logging
import os
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from pyrogram.errors import FloodWait, MessageNotModified
import sqlite3
import traceback

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DigitalStoreBot")

# Konfigurasi API dan Token
API_ID = 29386534  # Ganti dengan API ID kamu
API_HASH = "8f35dec4c4de801ec648cf4ca1cf04e9"
BOT_TOKEN = "7766823813:AAHOtLoVip5vxtKbwly1kt3JTX7FwN1Ko_M"

# ID Admin dan Channel Log
ADMIN_IDS = [6467919046, 1407585501]  # Ganti dengan ID admin
LOG_CHANNEL = -1002220134973  # Ganti dengan ID channel log

# Direktori untuk menyimpan cache gambar dan file sementara
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Inisialisasi database
class Database:
    def __init__(self, db_name="database.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.setup_tables()
        logger.info("[INFO] Database berhasil diinisialisasi")
        
    def setup_tables(self):
        """Membuat tabel-tabel yang diperlukan jika belum ada"""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price TEXT NOT NULL,
            delivery TEXT,
            image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            proof_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        """)
        
        self.conn.commit()
    
    def get_products(self):
        """Mengambil semua produk dari database"""
        self.cursor.execute("SELECT id, name FROM products ORDER BY id DESC")
        return self.cursor.fetchall()
    
    def get_product(self, product_id):
        """Mengambil detail produk berdasarkan ID"""
        self.cursor.execute("SELECT name, description, price, delivery, image FROM products WHERE id = ?", (product_id,))
        return self.cursor.fetchone()
    
    def get_payment_methods(self):
        """Mengambil semua metode pembayaran"""
        self.cursor.execute("SELECT method, details FROM payments")
        return self.cursor.fetchall()
    
    def add_product(self, name, description, price, delivery="", image=""):
        """Menambahkan produk baru"""
        self.cursor.execute(
            "INSERT INTO products (name, description, price, delivery, image) VALUES (?, ?, ?, ?, ?)",
            (name, description, price, delivery, image)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def add_payment_method(self, method, details=""):
        """Menambahkan metode pembayaran baru"""
        self.cursor.execute("INSERT INTO payments (method, details) VALUES (?, ?)", (method, details))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def delete_product(self, product_id):
        """Menghapus produk berdasarkan ID"""
        self.cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        return rows_affected
    
    def delete_payment_method(self, method):
        """Menghapus metode pembayaran"""
        self.cursor.execute("DELETE FROM payments WHERE method = ?", (method,))
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        return rows_affected
    
    def add_order(self, user_id, product_id, payment_method, proof_file_id):
        """Menambahkan pesanan baru"""
        self.cursor.execute(
            "INSERT INTO orders (user_id, product_id, payment_method, proof_file_id) VALUES (?, ?, ?, ?)",
            (user_id, product_id, payment_method, proof_file_id)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_orders(self, status=None):
        """Mengambil semua pesanan dengan filter status opsional"""
        if status:
            self.cursor.execute("""
                SELECT o.id, o.user_id, o.product_id, p.name as product_name, 
                o.payment_method, o.proof_file_id, o.status, o.created_at
                FROM orders o
                JOIN products p ON o.product_id = p.id
                WHERE o.status = ?
                ORDER BY o.created_at DESC
            """, (status,))
        else:
            self.cursor.execute("""
                SELECT o.id, o.user_id, o.product_id, p.name as product_name, 
                o.payment_method, o.proof_file_id, o.status, o.created_at
                FROM orders o
                JOIN products p ON o.product_id = p.id
                ORDER BY o.created_at DESC
            """)
        return self.cursor.fetchall()
    
    def update_order_status(self, order_id, status):
        """Mengupdate status pesanan"""
        self.cursor.execute(
            "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, order_id)
        )
        self.conn.commit()
        return self.cursor.rowcount
    
    def close(self):
        """Menutup koneksi database"""
        self.conn.close()
        logger.info("[INFO] Koneksi database ditutup")

# Inisialisasi bot dan database
db = Database()
bot = Client("digital_store_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
# Menyimpan data sementara pengguna
user_state = {}


# Fungsi utilitas untuk menangani error
async def send_error_log(client, error, context=""):
    """Mengirim log error ke channel log"""
    error_message = f"⚠️ ERROR TERJADI ⚠️\n\n{context}\n\n{str(error)}\n\n{traceback.format_exc()}"
    try:
        await client.send_message(LOG_CHANNEL, error_message)
        logger.error(f"[ERROR] {error_message}")
    except Exception as e:
        logger.error(f"[ERROR] Gagal mengirim log error: {str(e)}")


# Handler untuk command /start
@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    try:
        user = message.from_user
        logger.info(f"[INFO] User {user.id} ({user.first_name}) menggunakan command /start")
        
        # Cek jika ada parameter pada command /start
        if len(message.command) > 1:
            # Implementasi referral atau deep linking bisa ditambahkan di sini
            pass
        
        # Buat tombol untuk katalog dan bantuan
        buttons = [
            [InlineKeyboardButton("🛒 Katalog Produk", callback_data="view_catalog")],
            [InlineKeyboardButton("❓ Bantuan", callback_data="help")]
        ]
        
        # Jika pengguna adalah admin, tambahkan tombol admin panel
        if message.from_user.id in ADMIN_IDS:
            buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
            
        welcome_text = (
            f"Selamat datang {message.from_user.mention} di Digital Store Bot!\n\n"
            f"Bot ini menyediakan berbagai produk digital yang bisa kamu beli dengan mudah.\n"
            f"Pilih opsi di bawah untuk melanjutkan:"
        )
        
        await message.reply(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await send_error_log(client, e, f"Command /start oleh {message.from_user.id}")
        await message.reply("Terjadi kesalahan. Silakan coba lagi nanti.")


# Handler untuk katalog produk
@bot.on_callback_query(filters.regex("^view_catalog$"))
async def view_catalog(client, callback_query: CallbackQuery):
    try:
        logger.info(f"[INFO] User {callback_query.from_user.id} melihat katalog produk")
        products = db.get_products()
        
        if not products:
            await callback_query.message.edit_text(
                "Belum ada produk tersedia. Silakan cek kembali nanti.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_start")]])
            )
            return
        
        buttons = []
        for product in products:
            buttons.append([InlineKeyboardButton(product["name"], callback_data=f"buy_{product['id']}")])
        
        # Tambahkan tombol kembali
        buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_start")])
        
        await callback_query.message.edit_text(
            "🛒 **Katalog Produk**\n\nPilih produk yang ingin kamu beli:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        # Abaikan error jika pesan tidak dimodifikasi
        pass
    except Exception as e:
        await send_error_log(client, e, f"View catalog oleh {callback_query.from_user.id}")
        await callback_query.answer("Terjadi kesalahan. Silakan coba lagi.", show_alert=True)


# Handler untuk kembali ke menu utama
@bot.on_callback_query(filters.regex("^back_to_start$"))
async def back_to_start(client, callback_query: CallbackQuery):
    try:
        buttons = [
            [InlineKeyboardButton("🛒 Katalog Produk", callback_data="view_catalog")],
            [InlineKeyboardButton("❓ Bantuan", callback_data="help")]
        ]
        
        # Jika pengguna adalah admin, tambahkan tombol admin panel
        if callback_query.from_user.id in ADMIN_IDS:
            buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
            
        welcome_text = (
            f"Selamat datang {callback_query.from_user.mention} di Digital Store Bot!\n\n"
            f"Bot ini menyediakan berbagai produk digital yang bisa kamu beli dengan mudah.\n"
            f"Pilih opsi di bawah untuk melanjutkan:"
        )
        
        await callback_query.message.edit_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        # Abaikan error jika pesan tidak dimodifikasi
        pass
    except Exception as e:
        await send_error_log(client, e, f"Back to start oleh {callback_query.from_user.id}")


# Handler untuk bantuan
@bot.on_callback_query(filters.regex("^help$"))
async def help_command(client, callback_query: CallbackQuery):
    try:
        help_text = (
            "🔍 **Bantuan Penggunaan Bot**\n\n"
            "Bot ini memungkinkan kamu untuk membeli produk digital dengan langkah-langkah berikut:\n\n"
            "1. Pilih produk yang ingin dibeli dari katalog\n"
            "2. Pilih metode pembayaran yang tersedia\n"
            "3. Transfer sesuai dengan instruksi yang diberikan\n"
            "4. Kirim bukti pembayaran ke bot\n"
            "5. Tunggu konfirmasi dari admin\n"
            "6. Produk akan segera dikirimkan\n\n"
            "Jika ada pertanyaan atau kendala, silakan hubungi admin kami."
        )
        
        buttons = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_start")]]
        
        await callback_query.message.edit_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        # Abaikan error jika pesan tidak dimodifikasi
        pass
    except Exception as e:
        await send_error_log(client, e, f"Help command oleh {callback_query.from_user.id}")


# Handler untuk detail produk
@bot.on_callback_query(filters.regex("^buy_"))
async def product_detail(client, callback_query: CallbackQuery):
    try:
        product_id = int(callback_query.data.split("_")[1])
        logger.info(f"[INFO] User {callback_query.from_user.id} melihat detail produk ID {product_id}")
        
        product = db.get_product(product_id)
        if not product:
            await callback_query.answer("Produk tidak ditemukan.", show_alert=True)
            return
            
        name, desc, price, delivery, image = product
        
        payment_methods = db.get_payment_methods()
        if not payment_methods:
            await callback_query.message.edit_text(
                "Belum ada metode pembayaran tersedia. Silakan hubungi admin.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="view_catalog")]])
            )
            return
            
        buttons = []
        for method in payment_methods:
            buttons.append([InlineKeyboardButton(method[0], callback_data=f"pay_{product_id}_{method[0]}")])
            
        # Tambahkan tombol kembali
        buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="view_catalog")])
        
        product_text = (
            f"📦 **{name}**\n\n"
            f"📝 **Deskripsi:**\n{desc}\n\n"
            f"💰 **Harga:** {price}\n\n"
            f"Pilih metode pembayaran di bawah ini:"
        )
        
        if image:
            # Cek apakah message saat ini adalah foto
            if hasattr(callback_query.message, 'photo'):
                try:
                    await callback_query.message.edit_media(
                        media=InputMediaPhoto(image, caption=product_text),
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except Exception as e:
                    # Jika gagal edit, hapus pesan lama dan kirim yang baru
                    await callback_query.message.delete()
                    await client.send_photo(
                        callback_query.message.chat.id,
                        photo=image,
                        caption=product_text,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            else:
                # Jika message bukan foto, hapus dan kirim yang baru
                await callback_query.message.delete()
                await client.send_photo(
                    callback_query.message.chat.id,
                    photo=image,
                    caption=product_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
        else:
            # Jika tidak ada gambar, edit text saja
            await callback_query.message.edit_text(
                product_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except MessageNotModified:
        # Abaikan error jika pesan tidak dimodifikasi
        pass
    except Exception as e:
        await send_error_log(client, e, f"Product detail ID {product_id} oleh {callback_query.from_user.id}")
        await callback_query.answer("Terjadi kesalahan. Silakan coba lagi.", show_alert=True)


# Handler untuk pemilihan metode pembayaran
@bot.on_callback_query(filters.regex("^pay_"))
async def choose_payment(client, callback_query: CallbackQuery):
    try:
        _, pid, method = callback_query.data.split("_", 2)
        pid = int(pid)
        
        logger.info(f"[INFO] User {callback_query.from_user.id} memilih pembayaran produk ID {pid} dengan metode {method}")
        
        # Ambil detail metode pembayaran jika ada
        payment_details = ""
        db.cursor.execute("SELECT details FROM payments WHERE method = ?", (method,))
        result = db.cursor.fetchone()
        if result and result["details"]:
            payment_details = f"\n\n{result['details']}"
        
        # Ambil nama produk
        db.cursor.execute("SELECT name, price FROM products WHERE id = ?", (pid,))
        product = db.cursor.fetchone()
        
        if not product:
            await callback_query.answer("Produk tidak ditemukan.", show_alert=True)
            return
            
        payment_text = (
            f"💳 **Detail Pembayaran**\n\n"
            f"Produk: **{product['name']}**\n"
            f"Harga: **{product['price']}**\n"
            f"Metode: **{method}**{payment_details}\n\n"
            f"Setelah melakukan pembayaran, silakan klik tombol di bawah ini untuk mengirim bukti pembayaran."
        )
        
        buttons = [
            [InlineKeyboardButton("📤 Kirim Bukti Pembayaran", callback_data=f"upload_{pid}_{method}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"buy_{pid}")]
        ]
        
        await callback_query.message.edit_text(
            payment_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        # Abaikan error jika pesan tidak dimodifikasi
        pass
    except Exception as e:
        await send_error_log(client, e, f"Choose payment for product ID {pid} oleh {callback_query.from_user.id}")
        await callback_query.answer("Terjadi kesalahan. Silakan coba lagi.", show_alert=True)


# Handler untuk prompt upload bukti pembayaran
@bot.on_callback_query(filters.regex("^upload_"))
async def prompt_upload(client, callback_query: CallbackQuery):
    try:
        _, pid, method = callback_query.data.split("_", 2)
        pid = int(pid)
        
        logger.info(f"[INFO] User {callback_query.from_user.id} ingin mengirim bukti pembayaran untuk produk ID {pid}")
        
        # Simpan state pengguna
        user_state[callback_query.from_user.id] = {
            "product_id": pid,
            "payment_method": method,
            "waiting_for": "proof_photo"
        }
        
        upload_text = (
            f"📤 **Upload Bukti Pembayaran**\n\n"
            f"Silakan kirim foto bukti pembayaran untuk produk yang dipilih.\n"
            f"Pastikan foto jelas dan terdapat informasi lengkap tentang pembayaran."
        )
        
        buttons = [[InlineKeyboardButton("❌ Batal", callback_data=f"cancel_upload")]]
        
        await callback_query.message.edit_text(
            upload_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        # Abaikan error jika pesan tidak dimodifikasi
        pass
    except Exception as e:
        await send_error_log(client, e, f"Prompt upload for product ID {pid} oleh {callback_query.from_user.id}")
        await callback_query.answer("Terjadi kesalahan. Silakan coba lagi.", show_alert=True)


# Handler untuk pembatalan upload
@bot.on_callback_query(filters.regex("^cancel_upload$"))
async def cancel_upload(client, callback_query: CallbackQuery):
    try:
        # Hapus state pengguna
        if callback_query.from_user.id in user_state:
            del user_state[callback_query.from_user.id]
            
        logger.info(f"[INFO] User {callback_query.from_user.id} membatalkan upload bukti pembayaran")
        
        # Kembali ke menu utama
        await back_to_start(client, callback_query)
    except Exception as e:
        await send_error_log(client, e, f"Cancel upload oleh {callback_query.from_user.id}")
        await callback_query.answer("Terjadi kesalahan. Silakan coba lagi.", show_alert=True)


# Handler untuk menerima foto bukti pembayaran
@bot.on_message(filters.photo & filters.private)
async def upload_proof(client, message: Message):
    try:
        user_id = message.from_user.id
        
        # Cek apakah pengguna sedang dalam proses upload bukti
        if user_id not in user_state or user_state[user_id].get("waiting_for") != "proof_photo":
            return
            
        data = user_state[user_id]
        pid = data["product_id"]
        method = data["payment_method"]
        
        logger.info(f"[INFO] User {user_id} mengirim bukti pembayaran untuk produk ID {pid}")
        
        # Simpan file_id dari foto terbesar (kualitas terbaik)
        file_id = message.photo.file_id
        
        # Tambahkan order ke database
        order_id = db.add_order(user_id, pid, method, file_id)
        
        # Ambil detail produk
        product = db.get_product(pid)
        pname, _, price, delivery, _ = product
        
        # Kirim notifikasi ke channel log
        await client.send_photo(
            LOG_CHANNEL,
            photo=file_id,
            caption=(
                f"🔔 **PESANAN BARU #{order_id}**\n\n"
                f"👤 User: [{message.from_user.first_name}](tg://user?id={user_id})\n"
                f"📦 Produk: {pname}\n"
                f"💰 Harga: {price}\n"
                f"💳 Metode: {method}\n"
                f"⏱ Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
        )
        
        # Beritahu pengguna bahwa bukti telah diterima
        receipt_text = (
            f"✅ **Bukti Pembayaran Diterima**\n\n"
            f"ID Pesanan: #{order_id}\n"
            f"Produk: {pname}\n"
            f"Harga: {price}\n"
            f"Status: Menunggu konfirmasi admin\n\n"
            f"Pesanan Anda sedang diproses. Mohon tunggu konfirmasi dari admin."
        )
        
        await message.reply(receipt_text)
        
        # Jika ada delivery content, kirimkan ke pengguna setelah konfirmasi
        if product and delivery and delivery.strip():
            # Untuk saat ini, kirim produk secara otomatis
            # Pada implementasi nyata, sebaiknya tunggu admin mengkonfirmasi pembayaran
            delivery_text = (
                f"🎁 **Produk Anda Telah Siap**\n\n"
                f"Berikut adalah produk yang Anda beli:\n\n"
                f"{delivery}"
            )
            
            await message.reply(delivery_text)
            logger.info(f"[INFO] Produk ID {pid} berhasil dikirim ke user {user_id}")
            
            # Update status order menjadi completed
            db.update_order_status(order_id, "completed")
            
            # Kirim notifikasi ke channel log
            await client.send_message(
                LOG_CHANNEL,
                f"✅ **PESANAN #{order_id} SELESAI**\n\n"
                f"Produk telah dikirim otomatis ke pembeli."
            )
        
        # Hapus state pengguna
        del user_state[user_id]
        
    except Exception as e:
        await send_error_log(client, e, f"Upload proof oleh {message.from_user.id}")
        await message.reply("Terjadi kesalahan saat memproses bukti pembayaran. Silakan coba lagi nanti.")


# Handler untuk admin panel
@bot.on_callback_query(filters.regex("^admin_panel$"))
async def admin_panel(client, callback_query: CallbackQuery):
    try:
        # Cek apakah pengguna adalah admin
        if callback_query.from_user.id not in ADMIN_IDS:
            await callback_query.answer("Anda tidak memiliki akses ke panel admin.", show_alert=True)
            return
            
        logger.info(f"[INFO] Admin {callback_query.from_user.id} mengakses panel admin")
        
        admin_text = (
            "👑 **ADMIN PANEL**\n\n"
            "Silakan pilih opsi di bawah ini:"
        )
        
        buttons = [
            [InlineKeyboardButton("➕ Tambah Produk", callback_data="add_product")],
            [InlineKeyboardButton("➕ Tambah Metode Pembayaran", callback_data="add_payment")],
            [InlineKeyboardButton("🗂 Kelola Produk", callback_data="manage_products")],
            [InlineKeyboardButton("💳 Kelola Metode Pembayaran", callback_data="manage_payments")],
            [InlineKeyboardButton("📋 Lihat Pesanan", callback_data="view_orders")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_start")]
        ]
        
        await callback_query.message.edit_text(
            admin_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        # Abaikan error jika pesan tidak dimodifikasi
        pass
    except Exception as e:
        await send_error_log(client, e, f"Admin panel oleh {callback_query.from_user.id}")
        await callback_query.answer("Terjadi kesalahan. Silakan coba lagi.", show_alert=True)


# Handler untuk command /admin
@bot.on_message(filters.command("admin") & filters.user(ADMIN_IDS))
async def admin_command(client, message: Message):
    try:
        logger.info(f"[INFO] Admin {message.from_user.id} menggunakan command /admin")
        
        admin_text = (
            "👑 **ADMIN COMMANDS**\n\n"
            "Berikut adalah daftar perintah admin yang tersedia:\n\n"
            "/tambahproduk nama | deskripsi | harga | delivery | image_url\n"
            "/tambahmetode nama_metode | detail_metode\n"
            "/hapusproduk ID\n"
            "/hapusmetode nama_metode\n"
            "/orders - Melihat daftar pesanan\n"
            "/broadcast - Mengirim pesan ke semua pengguna"
        )
        
        buttons = [[InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]]
        
        await message.reply(
            admin_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await send_error_log(client, e, f"Admin command oleh {message.from_user.id}")
        await message.reply("Terjadi kesalahan. Silakan coba lagi nanti.")


# Handler untuk command tambah produk
@bot.on_message(filters.command("tambahproduk") & filters.user(ADMIN_IDS))
async def tambah_produk(client, message: Message):
    try:
        if len(message.text.split(" ", 1)) < 2:
            await message.reply(
                "Format salah. Gunakan:\n/tambahproduk nama | deskripsi | harga | delivery | image_url"
            )
            return
            
        _, data = message.text.split(" ", 1)
        parts = [x.strip() for x in data.split("|")]
        
        if len(parts) < 3:
            await message.reply(
                "Format salah. Minimal nama, deskripsi, dan harga harus diisi."
            )
            return
            
        nama = parts[0]
        deskripsi = parts[1]
        harga = parts[2]
        delivery = parts[3] if len(parts) > 3 else ""
        image = parts[4]
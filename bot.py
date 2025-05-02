import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import sqlite3

API_ID = 12345678  # Ganti dengan API ID kamu
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"

ADMIN_IDS = [1355077923, 1407585501]  # Ganti dengan ID admin
LOG_CHANNEL = -1001234567890  # Ganti dengan ID channel log

db = sqlite3.connect("database.db")
c = db.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    price TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    payment_method TEXT,
    proof_file_id TEXT,
    status TEXT
)
""")
db.commit()

bot = Client("digital_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    c.execute("SELECT id, name FROM products")
    rows = c.fetchall()
    if not rows:
        await message.reply("Belum ada produk tersedia.")
        return
    buttons = [[InlineKeyboardButton(row[1], callback_data=f"buy_{row[0]}")] for row in rows]
    await message.reply("Pilih produk yang ingin kamu beli:", reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_callback_query(filters.regex("^buy_"))
async def product_detail(client, callback_query: CallbackQuery):
    product_id = int(callback_query.data.split("_")[1])
    c.execute("SELECT name, description, price FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    if not product:
        await callback_query.answer("Produk tidak ditemukan.", show_alert=True)
        return
    name, desc, price = product
    c.execute("SELECT method FROM payments")
    payments = c.fetchall()
    buttons = [[InlineKeyboardButton(p[0], callback_data=f"pay_{product_id}_{p[0]}")] for p in payments]
    text = f"**{name}**\n{desc}\nHarga: {price}\n\nPilih metode pembayaran:"
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_callback_query(filters.regex("^pay_"))
async def choose_payment(client, callback_query: CallbackQuery):
    _, pid, method = callback_query.data.split("_", 2)
    pid = int(pid)
    await callback_query.message.edit_text(
        f"Kirim bukti pembayaran untuk produk ID {pid} (metode: {method}). Kirim sekarang."
    )
    bot.user_data[callback_query.from_user.id] = {"product_id": pid, "method": method}

@bot.on_message(filters.photo & filters.private)
async def upload_proof(client, message: Message):
    data = bot.user_data.get(message.from_user.id)
    if not data:
        await message.reply("Kamu belum memilih produk.")
        return
    pid = data["product_id"]
    method = data["method"]
    c.execute("INSERT INTO orders (user_id, product_id, payment_method, proof_file_id, status) VALUES (?, ?, ?, ?, ?)",
              (message.from_user.id, pid, method, message.photo.file_id, "pending"))
    db.commit()
    # Kirim ke channel log
    c.execute("SELECT name FROM products WHERE id = ?", (pid,))
    pname = c.fetchone()[0]
    await bot.send_photo(LOG_CHANNEL, message.photo.file_id,
                         caption=f"Pesanan Baru\nUser: [{message.from_user.first_name}](tg://user?id={message.from_user.id})\nProduk: {pname}\nMetode: {method}")
    await message.reply("Bukti pembayaran sudah diterima. Admin akan segera memproses pesananmu.")
    bot.user_data.pop(message.from_user.id)

@bot.on_message(filters.command("admin") & filters.user(ADMIN_IDS))
async def admin_panel(client, message: Message):
    await message.reply("Ketik perintah berikut:\n/tambahproduk nama | deskripsi | harga\n/tambahmetode nama_metode")

@bot.on_message(filters.command("tambahproduk") & filters.user(ADMIN_IDS))
async def tambah_produk(client, message: Message):
    try:
        _, data = message.text.split(" ", 1)
        nama, deskripsi, harga = [x.strip() for x in data.split("|")]
        c.execute("INSERT INTO products (name, description, price) VALUES (?, ?, ?)", (nama, deskripsi, harga))
        db.commit()
        await message.reply("Produk berhasil ditambahkan.")
    except:
        await message.reply("Format salah. Gunakan: /tambahproduk nama | deskripsi | harga")

@bot.on_message(filters.command("tambahmetode") & filters.user(ADMIN_IDS))
async def tambah_metode(client, message: Message):
    try:
        _, metode = message.text.split(" ", 1)
        c.execute("INSERT INTO payments (method) VALUES (?)", (metode.strip(),))
        db.commit()
        await message.reply("Metode pembayaran ditambahkan.")
    except:
        await message.reply("Format salah. Gunakan: /tambahmetode nama_metode")

if __name__ == "__main__":
    bot.user_data = {}
    bot.run()

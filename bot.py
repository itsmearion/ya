
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
import sqlite3

API_ID = 29386534 # Ganti dengan API ID kamu
API_HASH = "8f35dec4c4de801ec648cf4ca1cf04e9"
BOT_TOKEN = "7766823813:AAHOtLoVip5vxtKbwly1kt3JTX7FwN1Ko_M"

ADMIN_IDS = [6467919046, 1407585501]
# Ganti dengan ID admin
LOG_CHANNEL = -1001234567890 #Ganti dengan ID channel log

db = sqlite3.connect("database.db")
c = db.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    price TEXT,
    delivery TEXT,
    image TEXT
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
    c.execute("SELECT name, description, price, image FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    if not product:
        await callback_query.answer("Produk tidak ditemukan.", show_alert=True)
        return
    name, desc, price, image = product
    c.execute("SELECT method FROM payments")
    payments = c.fetchall()
    buttons = [[InlineKeyboardButton(p[0], callback_data=f"pay_{product_id}_{p[0]}")] for p in payments]
    text = f"{name}\n{desc}\nHarga: {price}\n\nPilih metode pembayaran:"
    if image:
        await callback_query.message.delete()
        await client.send_photo(callback_query.message.chat.id, image, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
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
    c.execute("SELECT name, delivery FROM products WHERE id = ?", (pid,))
    pname, delivery = c.fetchone()
    await bot.send_photo(LOG_CHANNEL, message.photo.file_id,
                         caption=f"Pesanan Baru\nUser: [{message.from_user.first_name}](tg://user?id={message.from_user.id})\nProduk: {pname}\nMetode: {method}")
    await message.reply("Bukti pembayaran sudah diterima. Admin akan segera memproses pesananmu.")
    if delivery:
        await message.reply(f"Berikut adalah produkmu:\n\n{delivery}")
    bot.user_data.pop(message.from_user.id)
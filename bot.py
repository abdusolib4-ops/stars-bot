import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
SUPPORT = os.getenv("SUPPORT_USERNAME", "@admin")
START_BONUS = 0  # keyinroq: birinchi xariddan keyin bonus beriladi

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# ---------- Ma'lumotlar bazasi ----------
db = sqlite3.connect("bot.db")
db.row_factory = sqlite3.Row
db.executescript(
    """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    balance INTEGER DEFAULT 0,
    orders_count INTEGER DEFAULT 0,
    referrer_id INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service TEXT,
    amount INTEGER,
    status TEXT DEFAULT 'new',
    created_at TEXT
);
"""
)
db.commit()


def get_user(uid):
    return db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def add_user(uid, username, full_name, referrer=None):
    if get_user(uid):
        return False
    db.execute(
        "INSERT INTO users (id, username, full_name, balance, referrer_id, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (uid, username, full_name, START_BONUS, referrer, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return True


def change_balance(uid, delta):
    db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (delta, uid))
    db.commit()


def fmt(n):
    return f"{n:,}".replace(",", " ")


# ---------- Menyular ----------
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍 Do'kon — barcha xizmatlar bir joyda", callback_data="shop")
    kb.button(text="📱 Raqam olish", callback_data="svc:number")
    kb.button(text="⭐ Stars olish", callback_data="svc:stars")
    kb.button(text="💎 Premium olish", callback_data="svc:premium")
    kb.button(text="🎁 Gift olish", callback_data="svc:gift")
    kb.button(text="👤 Profil", callback_data="profile")
    kb.button(text="🧾 Buyurtmalar", callback_data="orders")
    kb.button(text="🏆 Top", callback_data="top")
    kb.button(text="🆘 Qo'llab-quvvatlash", callback_data="support")
    kb.button(text="💳 Hisobni to'ldirish", callback_data="topup")
    kb.adjust(1, 1, 2, 1, 2, 2, 1)
    return kb.as_markup()


def shop_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 Raqam olish", callback_data="svc:number")
    kb.button(text="⭐ Stars olish", callback_data="svc:stars")
    kb.button(text="💎 Premium olish", callback_data="svc:premium")
    kb.button(text="🎁 Gift olish", callback_data="svc:gift")
    kb.button(text="⬅️ Orqaga", callback_data="back")
    kb.adjust(1, 2, 1, 1)
    return kb.as_markup()


def back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Orqaga", callback_data="back")
    return kb.as_markup()


async def show(call: CallbackQuery, text: str, markup):
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:
        await call.message.answer(text, reply_markup=markup)
    await call.answer()


# ---------- Buyruqlar ----------
@dp.message(CommandStart())
async def start(msg: Message):
    referrer = None
    parts = (msg.text or "").split()
    if len(parts) > 1 and parts[1].isdigit() and int(parts[1]) != msg.from_user.id:
        referrer = int(parts[1])
    add_user(msg.from_user.id, msg.from_user.username, msg.from_user.full_name, referrer)
    await msg.answer(
        f"Assalomu alaykum, {msg.from_user.full_name}! 👋\n\nQuyidagi menyudan keraklisini tanlang:",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await show(call, "Quyidagi menyudan keraklisini tanlang:", main_menu())


@dp.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    await show(call, "🛍 Do'kon — barcha xizmatlar bir joyda:", shop_menu())


@dp.callback_query(F.data.startswith("svc:"))
async def service(call: CallbackQuery):
    # 2-bosqichda shu yerga API ulanadi
    await show(call, "Bu xizmat tez orada qo'shiladi. ⏳", back_menu())


@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    u = get_user(call.from_user.id)
    if not u:
        add_user(call.from_user.id, call.from_user.username, call.from_user.full_name)
        u = get_user(call.from_user.id)
    me = await call.bot.get_me()
    text = (
        "👤 Profil\n\n"
        f"🆔 ID: {u['id']}\n"
        f"💰 Balans: {fmt(u['balance'])} so'm\n"
        f"🛒 Buyurtmalar: {u['orders_count']} ta\n"
        f"📅 Ro'yxatdan o'tgan: {u['created_at'][:10]}\n\n"
        f"🔗 Referal havolangiz:\nhttps://t.me/{me.username}?start={u['id']}"
    )
    await show(call, text, back_menu())


@dp.callback_query(F.data == "orders")
async def orders(call: CallbackQuery):
    rows = db.execute(
        "SELECT id, service, amount, status, created_at FROM orders "
        "WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (call.from_user.id,),
    ).fetchall()
    lines = [
        f"#{r['id']} · {r['service']} · {fmt(r['amount'])} so'm · {r['status']}" for r in rows
    ]
    text = "🧾 Buyurtmalar\n\n" + ("\n".join(lines) if lines else "Hozircha buyurtma yo'q.")
    await show(call, text, back_menu())


@dp.callback_query(F.data == "topup")
async def topup(call: CallbackQuery):
    # 3-bosqichda to'lov tizimi ulanadi
    text = (
        "💳 Hisobni to'ldirish\n\n"
        f"Hozircha to'ldirish uchun adminga murojaat qiling: {SUPPORT}\n"
        f"ID raqamingiz: {call.from_user.id}"
    )
    await show(call, text, back_menu())


@dp.callback_query(F.data == "top")
async def top(call: CallbackQuery):
    rows = db.execute(
        "SELECT full_name, orders_count FROM users ORDER BY orders_count DESC LIMIT 10"
    ).fetchall()
    lines = [f"{i}. {r['full_name']} — {r['orders_count']} ta" for i, r in enumerate(rows, 1)]
    text = "🏆 Top xaridorlar\n\n" + ("\n".join(lines) if lines else "Hozircha bo'sh.")
    await show(call, text, back_menu())


@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    await show(call, f"🆘 Savollar uchun: {SUPPORT}", back_menu())


# ---------- Admin ----------
@dp.message(Command("addbalance"))
async def addbalance(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    try:
        _, uid, amount = msg.text.split()
        uid, amount = int(uid), int(amount)
    except ValueError:
        await msg.answer("Format: /addbalance user_id summa")
        return
    if not get_user(uid):
        await msg.answer("Foydalanuvchi topilmadi.")
        return
    change_balance(uid, amount)
    await msg.answer(f"✅ {uid} balansiga {fmt(amount)} so'm qo'shildi.")
    try:
        await msg.bot.send_message(uid, f"💰 Balansingiz {fmt(amount)} so'mga to'ldirildi.")
    except Exception:
        pass


@dp.message(Command("stats"))
async def stats(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    n = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    await msg.answer(f"👥 Foydalanuvchilar: {n}")


async def main():
    if not TOKEN:
        raise SystemExit(".env faylda BOT_TOKEN yo'q")
    await dp.start_polling(Bot(TOKEN))


if __name__ == "__main__":
    asyncio.run(main())

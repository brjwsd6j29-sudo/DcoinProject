# bot.py — DKcoins Telegram-бот (aiogram 3)
import asyncio, sqlite3, time
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# ══════════ НАСТРОЙКИ ══════════
BOT_TOKEN   = "7688724556:AAGUWmLvh1V4lVnEbifjIpZTcFUqGLQlRFs"
ADMIN_ID    = 7895911575                        # свой ID (узнать: @userinfobot)
WEBAPP_URL  = "https://dcoinproject.netlify.app"  # адрес сайта с Netlify
DAILY       = 500
START_BAL   = 1000

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ══════════ БАЗА ДАННЫХ (SQLite) ══════════
db = sqlite3.connect("dkcoins.db", check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, name TEXT, username TEXT,
    balance REAL DEFAULT 1000, games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
    banned INTEGER DEFAULT 0, last_daily REAL DEFAULT 0)""")
db.commit()

def get_user(uid, name="", username=""):
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if row is None:
        db.execute("INSERT INTO users(id,name,username) VALUES(?,?,?)", (uid, name, username))
        db.commit()
        row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return row

class AdminStates(StatesGroup):
    amount = State()
    broadcast = State()

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 ИГРАТЬ", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="bal"),
         InlineKeyboardButton(text="🎁 Бонус", callback_data="daily")],
        [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top")],
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="a_stat"),
         InlineKeyboardButton(text="👥 Игроки", callback_data="a_users")],
        [InlineKeyboardButton(text="💰 Выдать монеты", callback_data="a_give")],
        [InlineKeyboardButton(text="✖️ Забрать монеты", callback_data="a_take")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="a_bc")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="a_close")],
    ])

# ══════════ КОМАНДЫ ══════════
@dp.message(CommandStart())
async def start(m: Message):
    if m.from_user.id != ADMIN_ID and db.execute(
        "SELECT banned FROM users WHERE id=?", (m.from_user.id,)).fetchone() and \
        db.execute("SELECT banned FROM users WHERE id=?", (m.from_user.id,)).fetchone()[0]:
        return await m.answer("🚫 Ты заблокирован администратором.")
    u = get_user(m.from_user.id, m.from_user.full_name, m.from_user.username or "")
    await m.answer(
        f"👋 <b>{m.from_user.first_name}</b>, добро пожаловать в <b>DKcoins</b>!\n\n"
        f"🪙 Твой баланс: <b>{u[3]:,.0f} DK</b>\n"
        f"🎁 Стартовый бонус уже начислен!\n\n"
        f"Жми «ИГРАТЬ» — внутри 3 игры: 🚀 Crash, 🪙 Flip, 🔻 Plinko",
        reply_markup=main_kb())

@dp.message(Command("balance"))
async def balance_cmd(m: Message):
    u = get_user(m.from_user.id)
    await m.answer(f"🪙 Баланс: <b>{u[3]:,.2f} DK</b>\n🎮 Игр: {u[4]} · 🏅 Побед: {u[5]}")

@dp.message(Command("daily"))
async def daily_cmd(m: Message):
    u = get_user(m.from_user.id)
    left = u[7] + 86400 - time.time()
    if left > 0:
        h, mn = int(left // 3600), int(left % 3600 // 60)
        return await m.answer(f"⏳ Бонус будет доступен через <b>{h}ч {mn}м</b>")
    db.execute("UPDATE users SET balance=balance+?, last_daily=? WHERE id=?", (DAILY, time.time(), m.from_user.id))
    db.commit()
    await m.answer(f"🎁 Ежедневный бонус: <b>+{DAILY} DK</b>!")

@dp.message(Command("top"))
async def top_cmd(m: Message):
    rows = db.execute("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 10").fetchall()
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>Топ игроков</b>\n\n" + "\n".join(
        f"{medals[i] if i < 3 else f'{i+1}.'} {r[0]} — <b>{r[1]:,.0f} DK</b>" for i, r in enumerate(rows))
    await m.answer(text)

# ══════════ КНОПКИ ══════════
@dp.callback_query(F.data.in_({"bal", "daily", "top"}))
async def cbs(c: CallbackQuery):
    u = get_user(c.from_user.id)
    if c.data == "bal":
        await c.message.answer(f"🪙 Баланс: <b>{u[3]:,.2f} DK</b>")
    elif c.data == "daily":
        left = u[7] + 86400 - time.time()
        if left > 0:
            h, mn = int(left // 3600), int(left % 3600 // 60)
            await c.message.answer(f"⏳ Бонус через <b>{h}ч {mn}м</b>")
        else:
            db.execute("UPDATE users SET balance=balance+?, last_daily=? WHERE id=?", (DAILY, time.time(), u[0]))
            db.commit()
            await c.message.answer(f"🎁 <b>+{DAILY} DK</b>!")
    else:
        await top_cmd(c.message)
    await c.answer()

# ══════════ АДМИН-МЕНЮ ══════════
@dp.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return await m.answer("🚫 Только для админа.")
    await m.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_kb())

pending_action = {}

@dp.callback_query(F.data.startswith("a_"))
async def admin_cbs(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("🚫", show_alert=True)
    if c.data == "a_close":
        await c.message.delete()
    elif c.data == "a_stat":
        cnt, total = db.execute("SELECT COUNT(*), SUM(balance) FROM users").fetchone()
        await c.message.answer(f"📊 <b>Статистика</b>\n👥 Игроков: <b>{cnt}</b>\n🪙 Монет у игроков: <b>{total or 0:,.0f} DK</b>")
    elif c.data == "a_users":
        rows = db.execute("SELECT name, balance, id FROM users ORDER BY balance DESC LIMIT 15").fetchall()
        await c.message.answer("👥 <b>Игроки:</b>\n\n" + "\n".join(
            f"• {r[0]} (ID <code>{r[2]}</code>) — <b>{r[1]:,.0f} DK</b>" for r in rows))
    elif c.data in ("a_give", "a_take"):
        pending_action[c.from_user.id] = c.data
        await state.set_state(AdminStates.amount)
        await c.message.answer("✍️ Пришли: <code>ID игрока сумма</code>\nНапример: <code>123456789 1000</code>")
    elif c.data == "a_bc":
        await state.set_state(AdminStates.broadcast)
        await c.message.answer("📢 Пришли текст рассылки — отправлю всем игрокам.")
    await c.answer()

@dp.message(AdminStates.amount)
async def admin_amount(m: Message, state: FSMContext):
    try:
        uid, amt = m.text.split()
        uid, amt = int(uid), float(amt)
    except Exception:
        return await m.answer("⚠️ Формат: <code>ID сумма</code>")
    if not db.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        return await m.answer("⚠️ Игрок не найден.")
    action = pending_action.get(m.from_user.id, "a_give")
    if action == "a_give":
        db.execute("UPDATE users SET balance=balance+? WHERE id=?", (amt, uid))
        await m.answer(f"✅ Выдал <b>{amt:,.0f} DK</b> игроку <code>{uid}</code>")
    else:
        db.execute("UPDATE users SET balance=MAX(0, balance-?) WHERE id=?", (amt, uid))
        await m.answer(f"✅ Забрал <b>{amt:,.0f} DK</b> у <code>{uid}</code>")
    db.commit()
    await state.clear()

@dp.message(AdminStates.broadcast)
async def admin_broadcast(m: Message, state: FSMContext):
    await state.clear()
    users = db.execute("SELECT id FROM users").fetchall()
    ok = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, f"📢 <b>DKcoins</b>\n\n{m.text}")
            ok += 1
        except Exception:
            pass
    await m.answer(f"📢 Рассылка доставлена: <b>{ok}</b> из {len(users)}")

async def main():
    print("🤖 DKcoins бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

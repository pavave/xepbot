# bot.py
"""
Telegram bot for selling your trading bot:
- registration, accept terms, wallet, ref link
- per-user mode: 'test' or 'real'
- store per-user exchange API keys (encrypted)
- /buy creates payment record (admin confirms)
- confirm payout gives 10% reward to referrer
- /trade executes (test=paper, real=via user's API keys) on Binance/Bybit via ccxt
"""
import os
import sqlite3
import secrets
import re
import asyncio
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from cryptography.fernet import Fernet, InvalidToken
import ccxt

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot_data.sqlite")
FERNET_KEY = os.getenv("FERNET_KEY")  # must be 32 url-safe base64 bytes, create with: Fernet.generate_key().decode()

if not BOT_TOKEN:
    raise RuntimeError("Set BOT_TOKEN in .env")
if not FERNET_KEY:
    raise RuntimeError("Set FERNET_KEY in .env (generate with Fernet.generate_key())")

fernet = Fernet(FERNET_KEY.encode())

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- DB ----------
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            wallet TEXT,
            ref_code TEXT UNIQUE,
            referrer_id INTEGER,
            accepted_terms INTEGER DEFAULT 0,
            active INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'test', -- 'test' or 'real'
            exchange TEXT NULL, -- 'binance' or 'bybit'
            api_key TEXT NULL, -- encrypted
            api_secret TEXT NULL, -- encrypted
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount INTEGER, -- minimal units (we use cents by default)
            status TEXT DEFAULT 'pending', -- pending | paid
            tx_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY,
            referrer_user_id INTEGER,
            referred_user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        con.commit()

def db_execute(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(query, params)
        con.commit()
        return cur

def db_fetchone(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(query, params)
        return cur.fetchone()

def db_fetchall(query, params=()):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(query, params)
        return cur.fetchall()

# ---------- Utils ----------
def gen_ref_code():
    return secrets.token_urlsafe(6)

def norm_amount_to_int(amount_str):
    try:
        amt = Decimal(amount_str)
    except:
        return None
    cents = int((amt * 100).quantize(Decimal('1'), rounding=ROUND_DOWN))
    return cents

def readable_from_cents(cents):
    return f"{(Decimal(cents) / 100):f}"

def is_valid_eth_address(addr: str):
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", addr.strip()))

def encrypt_val(plain: str):
    return fernet.encrypt(plain.encode()).decode()

def decrypt_val(token: str):
    try:
        return fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return None

# ---------- Bot handlers ----------
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    args = (message.text or "").partition(' ')[2].strip() or None
    existing = db_fetchone("SELECT id FROM users WHERE telegram_id = ?", (message.from_user.id,))
    if not existing:
        db_execute("INSERT INTO users (telegram_id) VALUES (?)", (message.from_user.id,))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять правила и продолжить", callback_data="accept_terms")]
    ])
    await message.answer("Привет! Это бот продажи трейдинг-бота. Нажми чтобы принять правила.", reply_markup=kb)

    # Apply referral if args is present and matches a ref_code
    if args:
        # treat args as ref_code
        row = db_fetchone("SELECT id FROM users WHERE ref_code = ?", (args,))
        if row:
            db_execute("UPDATE users SET referrer_id = ? WHERE telegram_id = ?", (row[0], message.from_user.id))

@dp.callback_query(lambda c: c.data == "accept_terms")
async def cb_accept(callback: types.CallbackQuery):
    uid = callback.from_user.id
    db_execute("UPDATE users SET accepted_terms = 1 WHERE telegram_id = ?", (uid,))
    await bot.answer_callback_query(callback.id, "Условия приняты. Введите ваш EVM-адрес (0x...):")
    await bot.send_message(uid, "Введите адрес кошелька (EVM):")

@dp.message()
async def any_message(message: types.Message):
    uid = message.from_user.id
    user = db_fetchone("SELECT id, accepted_terms, wallet FROM users WHERE telegram_id = ?", (uid,))
    if not user:
        await message.reply("Пожалуйста начните с /start")
        return
    user_id, accepted, wallet = user
    if accepted and not wallet:
        text = message.text.strip()
        if is_valid_eth_address(text):
            code = gen_ref_code()
            db_execute("UPDATE users SET wallet = ?, ref_code = ? WHERE telegram_id = ?", (text, code, uid))
            bot_username = (await bot.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start={code}"
            await message.reply(f"Адрес сохранён.\nТвоя реф-ссылка:\n{ref_link}\nЧтобы купить, используй /buy <сумма> (например: /buy 10.00)")
        else:
            await message.reply("Неверный адрес. Попробуй снова.")
        return
    # else ignore free messages

@dp.message(Command(commands=["mode"]))
async def cmd_mode(message: types.Message):
    uid = message.from_user.id
    args = (message.text or "").partition(' ')[2].strip().lower()
    if args not in ("test", "real", ""):
        await message.reply("Использование: /mode [test|real]\nПример: /mode test")
        return
    if args == "":
        row = db_fetchone("SELECT mode FROM users WHERE telegram_id = ?", (uid,))
        await message.reply(f"Текущий режим: {row[0] if row else 'test'}")
        return
    db_execute("UPDATE users SET mode = ? WHERE telegram_id = ?", (args, uid))
    await message.reply(f"Режим изменён на `{args}`. (test — бумажная торговля; real — реальные ордера при наличии ключей)")

@dp.message(Command(commands=["setexchange"]))
async def cmd_setexchange(message: types.Message):
    """
    Usage (three messages flow):
    /setexchange binance
    then bot asks for api key, then secret
    """
    uid = message.from_user.id
    args = (message.text or "").partition(' ')[2].strip().lower()
    if args not in ("binance", "bybit"):
        await message.reply("Использование: /setexchange [binance|bybit]\nПример: /setexchange binance")
        return
    # store exchange choice, ask for api key
    db_execute("UPDATE users SET exchange = ? WHERE telegram_id = ?", (args, uid))
    await message.reply("Отправь API_KEY (в следующем сообщении).")

    # wait next message - simple state via DB temp column could be used; to keep simple we do ephemeral wait
    def check(m: types.Message):
        return m.from_user.id == uid

    try:
        msg1 = await dp.wait_for(types.Message, timeout=120, check=check)
        api_key = msg1.text.strip()
        await message.reply("Теперь отправь API_SECRET (в следующем сообщении).")
        msg2 = await dp.wait_for(types.Message, timeout=120, check=check)
        api_secret = msg2.text.strip()
        # encrypt and save
        enc_key = encrypt_val(api_key)
        enc_sec = encrypt_val(api_secret)
        db_execute("UPDATE users SET api_key = ?, api_secret = ? WHERE telegram_id = ?", (enc_key, enc_sec, uid))
        await message.reply("Ключи сохранены (зашифрованы). Теперь можно тестировать /trade.")
    except asyncio.TimeoutError:
        await message.reply("Время ожидания истекло. Попробуйте снова /setexchange.")

def build_exchange_for_user(user_row):
    """
    user_row: (id, telegram_id, wallet, ref_code, referrer_id, accepted_terms, active, mode, exchange, api_key, api_secret,...)
    returns ccxt exchange instance configured or None
    """
    if not user_row:
        return None
    exchange_name = user_row[8]  # exchange column
    if not exchange_name:
        return None
    enc_key = user_row[9]
    enc_sec = user_row[10]
    if not enc_key or not enc_sec:
        return None
    api_key = decrypt_val(enc_key)
    api_secret = decrypt_val(enc_sec)
    if not api_key or not api_secret:
        return None
    # build ccxt instance
    try:
        if exchange_name == "binance":
            ex_class = ccxt.binance
            ex = ex_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            })
            # ccxt: for testnet (real) user must provide testnet keys or use special urls - we'll rely on user's keys
            return ex
        elif exchange_name == "bybit":
            ex_class = ccxt.bybit
            ex = ex_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            })
            return ex
    except Exception as e:
        print("build_exchange error:", e)
        return None

@dp.message(Command(commands=["trade"]))
async def cmd_trade(message: types.Message):
    """
    /trade SYMBOL SIDE AMOUNT
    example: /trade BTC/USDT buy 0.001
    Behavior:
      - if user's mode == 'test' -> simulate order and store as fake payment
      - if 'real' -> create order via user api keys (if present)
    """
    uid = message.from_user.id
    args = (message.text or "").partition(' ')[2].strip().split()
    if len(args) < 3:
        await message.reply("Использование: /trade SYMBOL SIDE AMOUNT\nПример: /trade BTC/USDT buy 0.001")
        return
    symbol, side, amount_str = args[0].upper(), args[1].lower(), args[2]
    amount = None
    try:
        amount = float(amount_str)
    except:
        await message.reply("Неверный amount")
        return
    user_row = db_fetchone("SELECT * FROM users WHERE telegram_id = ?", (uid,))
    if not user_row:
        await message.reply("Сначала /start и введи кошелёк")
        return
    mode = user_row[7] or 'test'
    if mode == 'test':
        # simulate execution price: fetch ticker from public market (no API key needed)
        try:
            public_bin = ccxt.binance()
            ticker = public_bin.fetch_ticker(symbol)
            price = ticker['last']
        except Exception:
            price = None
        await message.reply(f"[PAPER] Симуляция ордера {side.upper()} {symbol} {amount} @ {price if price else 'market'} — выполнено (симуляция).")
        return
    # real mode:
    ex = build_exchange_for_user(user_row)
    if not ex:
        await message.reply("У тебя не настроены ключи биржи. Настрой через /setexchange <binance|bybit>.")
        return
    try:
        # market order
        order = ex.create_order(symbol, 'market', side, amount)
        await message.reply(f"Ордер отправлен: {order}")
    except Exception as e:
        await message.reply(f"Ошибка при выставлении ордера: {e}")

@dp.message(Command(commands=["buy"]))
async def cmd_buy(message: types.Message):
    uid = message.from_user.id
    args = (message.text or "").partition(' ')[2].strip()
    if not args:
        await message.reply("Использование: /buy <amount> (например /buy 10.00)")
        return
    cents = norm_amount_to_int(args)
    if cents is None or cents <= 0:
        await message.reply("Неверная сумма")
        return
    row = db_fetchone("SELECT id, referrer_id FROM users WHERE telegram_id = ?", (uid,))
    if not row:
        await message.reply("Сначала /start")
        return
    user_id, referrer_id = row
    cur = db_execute("INSERT INTO payments (user_id, amount, status) VALUES (?, ?, 'pending')", (user_id, cents))
    payment_id = cur.lastrowid
    await message.reply(
        f"Создан платёж #{payment_id}. Пожалуйста, отправьте {readable_from_cents(cents)} USDC на ваш тест-адрес/контракт.\n"
        f"Когда оплатишь — попроси админа подтвердить транзакцию: /confirm {payment_id} <tx_hash>"
    )

@dp.message(Command(commands=["confirm"]))
async def cmd_confirm(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Только админ.")
        return
    args = (message.text or "").partition(' ')[2].strip().split()
    if len(args) < 2:
        await message.reply("Использование: /confirm <payment_id> <tx_hash>")
        return
    pid = int(args[0]); tx = args[1]
    row = db_fetchone("SELECT id, user_id, amount, status FROM payments WHERE id = ?", (pid,))
    if not row:
        await message.reply("Платёж не найден.")
        return
    if row[3] == 'paid':
        await message.reply("Уже отмечен как оплачен.")
        return
    db_execute("UPDATE payments SET status = 'paid', tx_hash = ? WHERE id = ?", (tx, pid))
    user_id = row[1]
    # activate user
    db_execute("UPDATE users SET active = 1 WHERE id = ?", (user_id,))
    # compute ref reward 10%
    urow = db_fetchone("SELECT referrer_id FROM users WHERE id = ?", (user_id,))
    referrer = urow[0] if urow else None
    if referrer:
        reward = (int(row[2]) * 10) // 100
        db_execute("INSERT INTO rewards (referrer_user_id, referred_user_id, amount, status) VALUES (?, ?, ?, 'pending')", (referrer, user_id, reward))
    await message.reply(f"Платёж {pid} подтверждён. Пользователь активирован, реф начислен (если есть).")

@dp.message(Command(commands=["my_refs"]))
async def cmd_myrefs(message: types.Message):
    uid = message.from_user.id
    row = db_fetchone("SELECT id FROM users WHERE telegram_id = ?", (uid,))
    if not row:
        await message.reply("Не зарегистрирован.")
        return
    user_id = row[0]
    cnt = db_fetchone("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))[0]
    total = db_fetchone("SELECT COALESCE(SUM(amount),0) FROM rewards WHERE referrer_user_id = ?", (user_id,))[0]
    await message.reply(f"Рефералов: {cnt}\nНачислено (миним. ед.): {total}\nОжидаемая выплата: {readable_from_cents(total)}")

@dp.message(Command(commands=["leaderboard"]))
async def cmd_leaderboard(message: types.Message):
    rows = db_fetchall("""
        SELECT u.telegram_id, u.ref_code, COALESCE(SUM(r.amount),0) total
        FROM users u
        LEFT JOIN rewards r ON r.referrer_user_id = u.id
        GROUP BY u.id
        ORDER BY total DESC
        LIMIT 10
    """)
    if not rows:
        await message.reply("Нет данных.")
        return
    text = "🏆 Лидерборд:\n"
    for i, r in enumerate(rows, start=1):
        tg, code, total = r
        text += f"{i}. tg:{tg} — {readable_from_cents(total)} — code:{code}\n"
    await message.reply(text)

# ---------- startup ----------
async def on_startup():
    init_db()
    print("DB inited")

if __name__ == "__main__":
    init_db()
    dp.startup.register(on_startup)
    print("Bot is running...")
    try:
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("Stopped")

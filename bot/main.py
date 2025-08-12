# bot/bot.py
import asyncio
import secrets
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_ID, CONTRACT_ADDRESS, USDC_ADDRESS
from backend.db import init_db, db_execute, db_fetchone
from backend.listener import start_listener
from decimal import Decimal, ROUND_DOWN

# --- utils ---
def gen_ref_code():
    return secrets.token_hex(8)

def norm_amount_to_int(amount_str):
    try:
        amt = Decimal(amount_str)
    except:
        return None
    cents = int((amt * 100).quantize(Decimal('1'), rounding=ROUND_DOWN))
    return cents

def readable_from_cents(cents):
    return f"{(Decimal(cents) / 100):f}"

# --- bot init ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command(commands=["start"]))
async def cmd_start(message):
    uid = message.from_user.id
    existing = db_fetchone("SELECT id FROM users WHERE telegram_id = ?", (uid,))
    if not existing:
        db_execute("INSERT INTO users (telegram_id) VALUES (?)", (uid,))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять правила и продолжить", callback_data="accept_terms")]
    ])
    await message.answer("Привет! Нажми чтобы принять правила.", reply_markup=kb)

@dp.message()
async def any_msg(message):
    # placeholder to capture wallet entry if needed; adapt to your flow
    pass

@dp.message(Command(commands=["buy"]))
async def cmd_buy(message):
    uid = message.from_user.id
    args = (message.text or "").partition(' ')[2].strip()
    if not args:
        await message.reply("Использование: /buy <amount> (например /buy 10.00)")
        return
    cents = norm_amount_to_int(args)
    if cents is None or cents <= 0:
        await message.reply("Неверная сумма")
        return
    row = db_fetchone("SELECT id FROM users WHERE telegram_id = ?", (uid,))
    if not row:
        await message.reply("Сначала /start")
        return
    user_id = row[0]
    ref = gen_ref_code()
    cur = db_execute("INSERT INTO payments (user_id, amount, ref, status) VALUES (?, ?, ?, 'pending')", (user_id, cents, ref))
    payment_id = cur.lastrowid

    # Provide payment instructions: approve + call contract.pay(ref) or transfer depending on contract
    msg = (
        f"Создан платёж #{payment_id}\n"
        f"Сумма: {readable_from_cents(cents)} USDC\n"
        f"Ref: `{ref}`\n\n"
        f"Инструкция (пример):\n"
        f"1) Убедитесь, что у вас есть тестовый USDC на сети и вы подключены к Sepolia/Base Sepolia.\n"
        f"2) Если контракт поддерживает вызов pay(ref), сначала approve USDC -> контракт, затем вызовите `pay(ref)`.\n"
        f"   Адрес приёма: {CONTRACT_ADDRESS}\n\n"
        f"Если вы не можете вызвать функцию контракта — пришлите tx хеш/скрин, админ подтвердит вручную (/confirm <id> <tx_hash>)."
    )
    await message.reply(msg)

@dp.message(Command(commands=["confirm"]))
async def cmd_confirm(message):
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
    db_execute("UPDATE users SET active = 1 WHERE id = ?", (user_id,))
    # reward handling omitted (can reuse code from before)
    await message.reply(f"Платёж {pid} подтверждён. Пользователь активирован.")

# startup
async def on_startup():
    init_db()
    # start background listener
    asyncio.create_task(start_listener(bot))
    print("Bot started and listener task launched")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    dp.startup.register(on_startup)
    try:
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("Stopped")


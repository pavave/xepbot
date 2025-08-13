import re
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from backend.db import init_db, add_user, get_user_by_telegram_id, get_user_by_referral_code
from bot.referral import save_referral

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

wallet_pattern = re.compile(r"^0x[a-fA-F0-9]{40}$")

init_db()

BOT_LINK = "https://t.me/ts4u_bot"

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    args = message.get_args()
    user = get_user_by_telegram_id(message.from_user.id)
    if user:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="КУПИТЬ за 100 USDC", callback_data="buy_100_usdc")]
        ])
        await message.answer(
            f"Привет снова!\nТвой кошелёк: {user['wallet_address']}\n"
            f"Твоя реферальная ссылка: {BOT_LINK}?start={user['referral_code']}",
            reply_markup=keyboard
        )
    else:
        await message.answer("Привет! Отправь, пожалуйста, адрес своего Ethereum-кошелька (начинается с 0x...)")
        dp.current_referrer_code = args if args else None

@dp.message()
async def wallet_handler(message: types.Message):
    if wallet_pattern.match(message.text):
        user = get_user_by_telegram_id(message.from_user.id)
        if user:
            await message.answer("Ты уже зарегистрирован.")
            return

        referrer_code = getattr(dp, "current_referrer_code", None)
        if referrer_code:
            ref_user = get_user_by_referral_code(referrer_code)
            if not ref_user:
                referrer_code = None

        referral_code = save_referral(add_user, message.from_user.id, message.text, referrer_code)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="КУПИТЬ за 100 USDC", callback_data="buy_100_usdc")]
        ])

        await message.answer(
            f"Адрес сохранён!\nТвоя реферальная ссылка:\n{BOT_LINK}?start={referral_code}",
            reply_markup=keyboard
        )
    else:
        await message.answer("Некорректный адрес кошелька. Попробуй ещё раз.")

@dp.callback_query(lambda c: c.data == "buy_100_usdc")
async def buy_usdc_callback(callback_query: types.CallbackQuery):
    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user:
        await callback_query.answer("Сначала зарегистрируй кошелек через /start", show_alert=True)
        return

    # Тут можно добавить вызов функции оплаты через смарт-контракт
    await callback_query.answer("Покупка 100 USDC (тест) инициирована!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

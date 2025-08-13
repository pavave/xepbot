import re
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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

# Хранение временного referrer кода в памяти (в реальном проекте надо в БД)
temp_referrals = {}

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    args = message.get_args()  # реферальный код из ссылки /start=refcode

    user = get_user_by_telegram_id(message.from_user.id)
    if user:
        # Если пользователь есть — привет и инфо
        await message.answer(
            f"Привет снова!\nТвой кошелёк: {user['wallet_address']}\n"
            f"Твоя реферальная ссылка: https://t.me/твой_бот?start={user['referral_code']}"
        )
        # Отправим кнопку "КУПИТЬ"
        buy_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="КУПИТЬ за 100 USDC")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer("Выбери действие:", reply_markup=buy_kb)

    else:
        # Если новый — просим адрес кошелька
        if args:
            temp_referrals[message.from_user.id] = args
        await message.answer("Привет! Отправь, пожалуйста, адрес своего Ethereum-кошелька (начинается с 0x...)")

@dp.message()
async def wallet_handler(message: types.Message):
    # Проверяем, что это адрес кошелька
    if wallet_pattern.match(message.text):
        user = get_user_by_telegram_id(message.from_user.id)
        if user:
            await message.answer("Ты уже зарегистрирован.")
            return

        # Получаем реферальный код если есть
        referrer_code = temp_referrals.pop(message.from_user.id, None)
        if referrer_code:
            ref_user = get_user_by_referral_code(referrer_code)
            if not ref_user:
                referrer_code = None

        # Сохраняем пользователя и рефералку
        referral_code = save_referral(add_user, message.from_user.id, message.text, referrer_code)
        await message.answer(
            f"Адрес сохранён!\nТвоя реферальная ссылка:\nhttps://t.me/твой_бот?start={referral_code}"
        )

        # Отправляем кнопку "КУПИТЬ"
        buy_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="КУПИТЬ за 100 USDC")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer("Выбери действие:", reply_markup=buy_kb)

    elif message.text == "КУПИТЬ за 100 USDC":
        await message.answer("Здесь пока должна быть логика оплаты через смарт-контракт. Пока в разработке.")

    else:
        await message.answer("Некорректный адрес кошелька. Попробуй ещё раз.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

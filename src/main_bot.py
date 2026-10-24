import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from dotenv import load_dotenv

from database import close_db, get_or_create_user, init_db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
PROXY_URL = os.getenv("PROXY_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL не задан в .env")

dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_or_create_user(
        message.from_user.id, message.from_user.username
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Играть", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
    )
    await message.answer(
        f"Добро пожаловать в Русскую рулетку!\n"
        f"Твой баланс: ${user['balance']:.2f}",
        reply_markup=keyboard,
    )


async def main():
    logging.basicConfig(level=logging.INFO)

    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
    bot = Bot(token=BOT_TOKEN, session=session)

    await init_db()
    try:
        await dp.start_polling(bot)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from handlers.start_handler import start_router
from handlers.olx_parser_handler import olx_parser_router
from handlers.search_handler import search_router
from utils.auto_update import auto_update

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(start_router)
dp.include_router(olx_parser_router)
dp.include_router(search_router)

async def main():
    logging.basicConfig(level=logging.INFO)
    # Если нужен автообновляемый процесс, раскомментируйте следующую строку:
    # asyncio.create_task(auto_update())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

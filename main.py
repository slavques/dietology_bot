import os
import logging

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

from app.db import init_db
from app.handlers import start, photo, callbacks, history, stats

API_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


def register_handlers():
    start.setup(dp)
    photo.setup(dp)
    callbacks.setup(dp)
    history.setup(dp)
    stats.setup(dp)


def main():
    init_db()
    register_handlers()
    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()

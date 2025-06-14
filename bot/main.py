import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

from .config import API_TOKEN
from .handlers import start, photo, history, stats, callbacks

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# register handlers
start.register(dp)
photo.register(dp)
history.register(dp)
stats.register(dp)
callbacks.register(dp)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

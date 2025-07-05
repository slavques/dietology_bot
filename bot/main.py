import logging
import logging.handlers
import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import API_TOKEN, SUBSCRIPTION_CHECK_INTERVAL, LOG_DIR
from .handlers import start, photo, history, stats, callbacks, faq, admin, subscription, manual
from .subscriptions import subscription_watcher
from .cleanup import cleanup_watcher
from .error_handler import handle_error

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# register handlers
start.register(dp)
photo.register(dp)
history.register(dp)
stats.register(dp)
callbacks.register(dp)
faq.register(dp)
admin.register(dp)
subscription.register(dp)
manual.register(dp)

dp.errors.register(handle_error)

async def main() -> None:
    watcher = subscription_watcher(bot, check_interval=SUBSCRIPTION_CHECK_INTERVAL)()
    cleanup = cleanup_watcher()()
    tasks = [
        asyncio.create_task(watcher),
        asyncio.create_task(cleanup),
    ]
    await dp.start_polling(bot)
    for t in tasks:
        t.cancel()


if __name__ == '__main__':
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, 'bot.log')
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when='D', backupCount=3
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, logging.StreamHandler()]
    )
    asyncio.run(main())

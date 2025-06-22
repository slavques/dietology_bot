import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import API_TOKEN
from .handlers import start, photo, history, stats, callbacks, faq, admin, subscription
from .subscriptions import subscription_watcher
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

dp.errors.register(handle_error)

async def main() -> None:
    watcher = subscription_watcher(bot)()
    task = asyncio.create_task(watcher)
    await dp.start_polling(bot)
    task.cancel()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

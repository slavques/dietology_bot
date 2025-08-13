import logging
import logging.handlers
import os
import asyncio
from datetime import datetime, time, timedelta, timezone
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import API_TOKEN, SUBSCRIPTION_CHECK_INTERVAL, LOG_DIR
from .handlers import start, photo, history, stats, callbacks, faq, admin, subscription, manual, reminders, referral
from .subscriptions import subscription_watcher
from .cleanup import cleanup_watcher
from .reminders import reminder_watcher
from .engagement import engagement_watcher
from .alerts import token_watcher, user_stats_watcher, setup_error_alerts
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
reminders.register(dp)
referral.register(dp)

dp.errors.register(handle_error)

async def main() -> None:
    watcher = subscription_watcher(bot, check_interval=SUBSCRIPTION_CHECK_INTERVAL)()
    cleanup = cleanup_watcher()()
    reminder = reminder_watcher()(bot)
    engage = engagement_watcher()(bot)
    tokens = token_watcher()
    stats = user_stats_watcher()
    tasks = [
        asyncio.create_task(watcher),
        asyncio.create_task(cleanup),
        asyncio.create_task(reminder),
        asyncio.create_task(engage),
        asyncio.create_task(tokens),
        asyncio.create_task(stats),
    ]
    await dp.start_polling(bot)
    for t in tasks:
        t.cancel()


if __name__ == '__main__':
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, 'bot.log')

    # Moscow timezone for log timestamps
    MSK = timezone(timedelta(hours=3))

    # Rotate logs at midnight Moscow time (21:00 server time)
    rotate_time = time(hour=21)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',
        backupCount=3,
        atTime=rotate_time,
    )

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    formatter.converter = lambda ts: datetime.fromtimestamp(ts, MSK).timetuple()

    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
    setup_error_alerts()

    asyncio.run(main())

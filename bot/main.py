import logging
import logging.handlers
import os
import re
import asyncio
from datetime import datetime, time, timedelta, timezone
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import API_TOKEN, SUBSCRIPTION_CHECK_INTERVAL, LOG_DIR
from .handlers import (
    start,
    photo,
    history,
    stats,
    callbacks,
    faq,
    admin,
    subscription,
    manual,
    reminders,
    referral,
    goals,
)
from .subscriptions import subscription_watcher
from .cleanup import cleanup_watcher
from .reminders import reminder_watcher
from .engagement import engagement_watcher
from .alerts import (
    token_watcher,
    user_stats_watcher,
    setup_error_alerts,
    setup_asyncio_error_alerts,
    create_monitored_task,
)
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
goals.register(dp)

dp.errors.register(handle_error)

async def main() -> None:
    loop = asyncio.get_running_loop()
    setup_asyncio_error_alerts(loop)

    watcher = subscription_watcher(bot, check_interval=SUBSCRIPTION_CHECK_INTERVAL)()
    cleanup = cleanup_watcher()()
    reminder = reminder_watcher()(bot)
    engage = engagement_watcher()(bot)
    tokens = token_watcher()
    stats = user_stats_watcher()
    tasks = [
        create_monitored_task(watcher, name="subscription_watcher"),
        create_monitored_task(cleanup, name="cleanup_watcher"),
        create_monitored_task(reminder, name="reminder_watcher"),
        create_monitored_task(engage, name="engagement_watcher"),
        create_monitored_task(tokens, name="token_watcher"),
        create_monitored_task(stats, name="user_stats_watcher"),
    ]
    try:
        await dp.start_polling(bot)
    except Exception:
        logging.exception("Polling stopped due to unexpected error")
        raise
    finally:
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
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d.log"

    base_name, base_ext = os.path.splitext(os.path.basename(log_file))

    # Ensure rotated logs follow the botYYYY-MM-DD.log convention expected by the alert bot.

    def _log_namer(default_name: str) -> str:
        directory, filename = os.path.split(default_name)
        prefix = f"{base_name}{base_ext}."
        if filename.startswith(prefix):
            timestamp_suffix = filename[len(prefix) :]
        else:
            # Fall back to removing the first dot-separated segment.
            _, _, timestamp_suffix = filename.partition(".")
        return os.path.join(directory, f"{base_name}{timestamp_suffix}")

    file_handler.namer = _log_namer
    file_handler.extMatch = re.compile(rf"^{re.escape(base_name)}\\d{{4}}-\\d{{2}}-\\d{{2}}\\.log$")

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

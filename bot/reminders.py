import asyncio
from datetime import datetime, timedelta, time
from aiogram import Bot

from .database import SessionLocal, User
from .logger import log


def _parse_time(value: str) -> time:
    try:
        h, m = map(int, value.split(":", 1))
        return time(hour=h, minute=m)
    except Exception:
        return time(hour=0, minute=0)


async def _send(bot: Bot, user: User, text: str) -> None:
    try:
        await bot.send_message(user.telegram_id, text)
        log("notification", "sent reminder to %s", user.telegram_id)
    except Exception:
        pass


def reminder_watcher(check_interval: int = 60):
    async def _watch(bot: Bot):
        while True:
            now = datetime.utcnow()
            session = SessionLocal()
            users = session.query(User).filter(User.timezone != None).all()
            for user in users:
                offset = timedelta(minutes=user.timezone or 0)
                local_now = now + offset
                if user.morning_enabled and user.morning_time:
                    target = _parse_time(user.morning_time)
                    if (user.last_morning is None or user.last_morning.date() != local_now.date()) and local_now.time().hour == target.hour and local_now.time().minute == target.minute:
                        await _send(bot, user, "🤖 Напоминание: утро!")
                        user.last_morning = local_now
                if user.day_enabled and user.day_time:
                    target = _parse_time(user.day_time)
                    if (user.last_day is None or user.last_day.date() != local_now.date()) and local_now.time().hour == target.hour and local_now.time().minute == target.minute:
                        await _send(bot, user, "🤖 Напоминание: день!")
                        user.last_day = local_now
                if user.evening_enabled and user.evening_time:
                    target = _parse_time(user.evening_time)
                    if (user.last_evening is None or user.last_evening.date() != local_now.date()) and local_now.time().hour == target.hour and local_now.time().minute == target.minute:
                        await _send(bot, user, "🤖 Напоминание: вечер!")
                        user.last_evening = local_now
            session.commit()
            session.close()
            await asyncio.sleep(check_interval)
    def _start(bot: Bot):
        return _watch(bot)
    return _start

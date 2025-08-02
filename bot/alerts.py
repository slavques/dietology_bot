import asyncio
import logging
from datetime import datetime, timedelta, time
from aiogram import Bot, Dispatcher, types

from .config import ALERT_BOT_TOKEN, ALERT_CHAT_ID as ALERT_CHAT_ID_CONFIG
from .database import (
    SessionLocal,
    User,
    Subscription,
    Payment,
    Meal,
    RequestLog,
    get_option,
    get_option_int,
    set_option,
)


alert_bot = Bot(token=ALERT_BOT_TOKEN) if ALERT_BOT_TOKEN else None
ALERT_CHAT_ID = ALERT_CHAT_ID_CONFIG or None


async def send_alert(text: str) -> None:
    """Send raw text to the alert chat if configured."""
    if not alert_bot or not ALERT_CHAT_ID:
        return
    try:
        await alert_bot.send_message(ALERT_CHAT_ID, text)
    except Exception:
        pass


class TokenMonitor:
    """Track daily token usage and emit alerts."""

    def __init__(self) -> None:
        today = datetime.utcnow().date()
        stored = get_option("tokens_date", today.isoformat())
        try:
            self.date = datetime.fromisoformat(stored).date()
        except Exception:
            self.date = today
        self.input = get_option_int("tokens_input", 0)
        self.output = get_option_int("tokens_output", 0)
        self.next_alert = get_option_int("tokens_next_alert", 1_000_000)

    def _save(self) -> None:
        set_option("tokens_date", self.date.isoformat())
        set_option("tokens_input", str(self.input))
        set_option("tokens_output", str(self.output))
        set_option("tokens_next_alert", str(self.next_alert))

    def _check_date(self) -> None:
        today = datetime.utcnow().date()
        if today != self.date:
            self.date = today
            self.input = 0
            self.output = 0
            self.next_alert = 1_000_000
            self._save()

    async def add(self, tokens_in: int, tokens_out: int) -> None:
        if tokens_in == 0 and tokens_out == 0:
            return
        if not alert_bot or not ALERT_CHAT_ID:
            return
        self._check_date()
        self.input += tokens_in
        self.output += tokens_out
        self._save()
        total = self.input + self.output
        if total >= self.next_alert:
            await send_alert(
                f"1млн токенов\nInput: {self.input}\nOutput: {self.output}\n"
            )
            self.next_alert += 1_000_000
            self._save()

    async def report_and_reset(self) -> None:
        if alert_bot and ALERT_CHAT_ID:
            total = self.input + self.output
            await send_alert(
                f"Отчет по токенам:\nInput: {self.input}\nOutput: {self.output}\nОбщее: {total}"
            )
        self.date = datetime.utcnow().date()
        self.input = 0
        self.output = 0
        self.next_alert = 1_000_000
        self._save()


token_monitor = TokenMonitor()


async def new_user(telegram_id: int) -> None:
    await send_alert(f"Новый пользователь {telegram_id}")


async def subscription_paid(
    telegram_id: int, count: int, tier: str, months: int
) -> None:
    await send_alert(
        f"Подписка оплачена {count}раз  {telegram_id} на {tier} {months} мес"
    )


async def user_left(telegram_id: int) -> None:
    await send_alert(f"Пользователь {telegram_id} вышел из бота")


async def gpt_error(message: str) -> None:
    await send_alert(f"Ошибка {message}")


async def anomalous_activity(telegram_id: int, n: int) -> None:
    await send_alert(f"Аномальная активность пользователя {telegram_id}: {n} запросов")


async def user_blocked_daily(telegram_id: int) -> None:
    await send_alert(
        f"Пользователь {telegram_id} заблокирован за 100 запросов в день"
    )


async def monthly_limit(telegram_id: int) -> None:
    await send_alert(
        f"Пользователь {telegram_id} пробил 800 запросов за текущий месяц"
    )


async def token_watcher() -> None:
    """Send daily token report at midnight UTC and reset counters."""
    while True:
        now = datetime.utcnow()
        tomorrow = now.date() + timedelta(days=1)
        midnight = datetime.combine(tomorrow, time())
        await asyncio.sleep((midnight - now).total_seconds())
        await token_monitor.report_and_reset()


async def user_stats_watcher() -> None:
    """Send daily user statistics to the alert chat at midnight UTC."""
    while True:
        now = datetime.utcnow()
        tomorrow = now.date() + timedelta(days=1)
        midnight = datetime.combine(tomorrow, time())
        await asyncio.sleep((midnight - now).total_seconds())

        session = SessionLocal()
        try:
            today = datetime.utcnow().date()
            start = datetime.combine(today - timedelta(days=1), time())
            end = datetime.combine(today, time())

            total_users = session.query(User).count()
            ended = (
                session.query(Subscription)
                .filter(
                    Subscription.period_end >= start,
                    Subscription.period_end < end,
                )
                .count()
            )
            new_users = (
                session.query(User)
                .filter(User.created_at >= start, User.created_at < end)
                .count()
            )
            paid_users = (
                session.query(Payment.user_id)
                .filter(Payment.timestamp >= start, Payment.timestamp < end)
                .distinct()
                .count()
            )

            report = "\n".join(
                [
                    "Статистика пользователей за сегодня",
                    "",
                    f"Всего пользователей: {total_users}",
                    f"Закончилась подписка: {ended}",
                    f"Новых пользователей : {new_users}",
                    f"Пользователей оплативших подписку: {paid_users}",
                ]
            )
            await send_alert(report)

            cutoff = datetime.utcnow() - timedelta(days=30)
            session.query(Meal).filter(Meal.timestamp < cutoff).delete()
            session.query(RequestLog).delete()
            session.commit()
        finally:
            session.close()


async def _log_chat_id(message: types.Message) -> None:
    chat_id = message.chat.id
    logging.info("[alert-bot] chat_id=%s", chat_id)
    await message.answer(f"Chat ID: {chat_id}")


async def run_alert_bot() -> None:
    if not alert_bot:
        raise RuntimeError("ALERT_BOT_TOKEN is not set")
    dp = Dispatcher()
    dp.message.register(_log_chat_id)
    await dp.start_polling(alert_bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_alert_bot())


import asyncio
import logging
import traceback
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Any, Iterable

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import FSInputFile

from sqlalchemy import func

from .config import (
    ALERT_BOT_TOKEN,
    ALERT_CHAT_IDS as ALERT_CHAT_IDS_CONFIG,
    LOG_DIR,
)
from .database import (
    SessionLocal,
    User,
    Subscription,
    Payment,
    Meal,
    get_option,
    get_option_int,
    set_option,
)
from .utils import sleep_until_next_utc_midnight


alert_bot = Bot(token=ALERT_BOT_TOKEN) if ALERT_BOT_TOKEN else None
ALERT_CHAT_IDS = ALERT_CHAT_IDS_CONFIG


async def send_alert(*texts: str) -> None:
    """Send raw text to all configured alert chats."""
    if not alert_bot or not ALERT_CHAT_IDS:
        return
    message = "".join(texts)
    for chat_id in ALERT_CHAT_IDS:
        try:
            await alert_bot.send_message(chat_id, message)
        except Exception:
            pass


class ErrorAlertHandler(logging.Handler):
    """Log handler that forwards error stack traces to alert chats."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - logging side effect
        if record.levelno < logging.ERROR:
            return
        if record.exc_info:
            trace = "".join(traceback.format_exception(*record.exc_info))
        else:
            trace = record.getMessage()
        message = f"Ошибка - {trace}"
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(send_alert(message))
        except RuntimeError:
            try:
                asyncio.run(send_alert(message))
            except Exception:
                pass


def setup_error_alerts() -> None:
    """Attach ErrorAlertHandler to root logger if alerting is enabled."""
    if alert_bot and ALERT_CHAT_IDS:
        logging.getLogger().addHandler(ErrorAlertHandler())


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
        if not alert_bot or not ALERT_CHAT_IDS:
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
        if alert_bot and ALERT_CHAT_IDS:
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


async def user_unblocked(telegram_id: int) -> None:
    await send_alert(f"Пользователь {telegram_id} разблокировал бота")


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
        await sleep_until_next_utc_midnight()
        await token_monitor.report_and_reset()


async def user_stats_watcher() -> None:
    """Send daily user statistics to the alert chat at midnight UTC."""
    while True:
        await sleep_until_next_utc_midnight()

        today = datetime.utcnow().date()
        start = datetime.combine(today - timedelta(days=1), time())
        end = datetime.combine(today, time())

        with SessionLocal() as session:
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

            requests_total = (
                session.query(func.sum(Subscription.daily_used)).scalar() or 0
            )

            report = "\n".join(
                [
                    "Статистика пользователей за сегодня",
                    "",
                    f"Всего пользователей: {total_users}",
                    f"Закончилась подписка: {ended}",
                    f"Новых пользователей : {new_users}",
                    f"Пользователей оплативших подписку: {paid_users}",
                    f"Запросов за сегодня: {requests_total}",
                ]
            )
            await send_alert(report)

            cutoff = datetime.utcnow() - timedelta(days=30)
            session.query(Meal).filter(Meal.timestamp < cutoff).delete()
            session.query(Subscription).update(
                {
                    "daily_used": 0,
                    "daily_start": datetime.utcnow(),
                }
            )
            session.commit()


async def _log_chat_id(message: types.Message) -> None:
    chat_id = message.chat.id
    logging.info("[alert-bot] chat_id=%s", chat_id)
    await message.answer(f"Chat ID: {chat_id}")


def _collect_log_files() -> list[Path]:
    """Return available log files sorted by modification time."""

    log_dir = Path(LOG_DIR)
    if not log_dir.exists():
        return []

    patterns: Iterable[str] = ("*.log", "*.log.*")
    files: dict[Path, Path] = {}
    for pattern in patterns:
        for path in log_dir.glob(pattern):
            if path.is_file():
                files[path.resolve()] = path

    return sorted(files.values(), key=lambda item: item.stat().st_mtime)


async def send_log_files(message: types.Message) -> None:
    """Send all available log files to the requesting alert chat."""

    if ALERT_CHAT_IDS and message.chat.id not in ALERT_CHAT_IDS:
        await message.answer("Команда недоступна в этом чате.")
        return

    log_files = _collect_log_files()
    if not log_files:
        await message.answer("Лог-файлы не найдены.")
        return

    await message.answer(f"Найдено {len(log_files)} лог-файлов, отправляю…")

    for path in log_files:
        try:
            await message.answer_document(
                FSInputFile(path), caption=path.name
            )
        except Exception:
            logging.exception("Failed to send log file %s", path)
            await message.answer(f"Не удалось отправить {path.name}.")
            break


def _logs_command_filter() -> Any:
    """Return a filter that matches /logs commands in text or caption."""

    pattern = r"^/logs(?:@\w+)?(?:\s|$)"
    return F.text.regexp(pattern) | F.caption.regexp(pattern)


async def run_alert_bot() -> None:
    if not alert_bot:
        raise RuntimeError("ALERT_BOT_TOKEN is not set")
    dp = Dispatcher()

    logs_filter = _logs_command_filter()

    dp.message.register(send_log_files, logs_filter)
    dp.message.register(_log_chat_id)

    dp.channel_post.register(send_log_files, logs_filter)
    dp.channel_post.register(_log_chat_id)
    await dp.start_polling(alert_bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_alert_bot())


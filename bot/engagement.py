import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot

from .database import SessionLocal, User, Meal, EngagementStatus
from .keyboards import subscribe_button, feedback_button
from .logger import log
from .messaging import send_with_retries
from .storage import pending_meals
from .settings import SUPPORT_HANDLE
from .texts import (
    WELCOME_REMINDER_15M,
    WELCOME_REMINDER_24H,
    WELCOME_REMINDER_3D,
    FIRST_REQUEST_DONE,
    THREE_REQUESTS_DONE,
    SEVEN_REQUESTS_DONE,
    FEEDBACK_10D,
    NO_MEAL_AFTER_REQUESTS,
    FREE_LIMIT_PAY_REMINDER,
    INACTIVE_7D,
    INACTIVE_14D,
    INACTIVE_30D,
    WELCOME_BACK,
    ADD_MEAL_REMINDER,
    BTN_REMOVE_LIMITS,
)


async def _send(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    event: Optional[str] = None,
    reply_markup=None,
    **kwargs,
) -> bool:
    """Send engagement messages with retries and logging."""

    send_kwargs = {}
    if reply_markup is not None:
        send_kwargs["reply_markup"] = reply_markup
    send_kwargs.update(kwargs)
    delivered = await send_with_retries(
        bot,
        chat_id,
        text=text,
        category="engagement",
        **send_kwargs,
    )
    label = event or text
    if delivered:
        log("engagement", "delivered %s to %s", label, chat_id)
    else:
        log("engagement", "failed to deliver %s to %s", label, chat_id)
    return delivered


async def process_request_events(bot: Bot, telegram_id: int) -> None:
    """Handle engagement events triggered by a new GPT request."""
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        session.close()
        return
    eng = user.engagement or EngagementStatus()
    if not user.engagement:
        user.engagement = eng
    now = datetime.utcnow()

    prev_ts = user.last_request

    if not eng.first_request_sent and user.requests_total >= 1:
        if await _send(
            bot,
            user.telegram_id,
            FIRST_REQUEST_DONE,
            event="first request milestone",
        ):
            eng.first_request_sent = True

    if not eng.three_requests_sent and user.requests_total >= 3:
        if await _send(
            bot,
            user.telegram_id,
            THREE_REQUESTS_DONE,
            event="three requests milestone",
        ):
            eng.three_requests_sent = True

    if not eng.seven_requests_sent and user.requests_total >= 7:
        if await _send(
            bot,
            user.telegram_id,
            SEVEN_REQUESTS_DONE,
            event="seven requests milestone",
        ):
            eng.seven_requests_sent = True

    if (
        not eng.five_no_meal_sent
        and user.requests_total >= 5
        and session.query(Meal).filter_by(user_id=user.id).count() == 0
    ):
        meals = [
            m
            for m in pending_meals.values()
            if m.get("chat_id") == user.telegram_id and m.get("message_id")
        ]
        msg_id = None
        if meals:
            latest = max(meals, key=lambda m: m.get("timestamp", 0))
            msg_id = latest.get("message_id")
        if await _send(
            bot,
            user.telegram_id,
            NO_MEAL_AFTER_REQUESTS,
            event="no meal reminder",
            reply_to_message_id=msg_id,
        ):
            eng.five_no_meal_sent = True

    if prev_ts and now - prev_ts >= timedelta(days=7):
        await _send(
            bot,
            user.telegram_id,
            WELCOME_BACK,
            event="welcome back reminder",
        )
    eng.inactivity_7d_sent = False
    eng.inactivity_14d_sent = False
    eng.inactivity_30d_sent = False

    user.last_request = now

    session.commit()
    session.close()


def engagement_watcher(check_interval: int = 60):
    async def _watch(bot: Bot):
        while True:
            now = datetime.utcnow()
            session = SessionLocal()
            users = session.query(User).all()
            for user in users:
                eng = user.engagement or EngagementStatus()
                if not user.engagement:
                    user.engagement = eng

                # no first request reminders
                if user.requests_total == 0:
                    delta = now - (user.created_at or now)
                    if (
                        not eng.no_request_15m
                        and delta >= timedelta(minutes=15)
                    ):
                        if await _send(
                            bot,
                            user.telegram_id,
                            WELCOME_REMINDER_15M,
                            event="welcome reminder 15m",
                        ):
                            eng.no_request_15m = True
                    if (
                        not eng.no_request_24h
                        and delta >= timedelta(hours=24)
                    ):
                        if await _send(
                            bot,
                            user.telegram_id,
                            WELCOME_REMINDER_24H,
                            event="welcome reminder 24h",
                        ):
                            eng.no_request_24h = True
                    if (
                        not eng.no_request_3d
                        and delta >= timedelta(days=3)
                    ):
                        if await _send(
                            bot,
                            user.telegram_id,
                            WELCOME_REMINDER_3D,
                            event="welcome reminder 3d",
                        ):
                            eng.no_request_3d = True

                # 10-day feedback
                if (
                    not eng.feedback_10d_sent
                    and now - (user.created_at or now) >= timedelta(days=10)
                ):
                    url = f"https://t.me/{SUPPORT_HANDLE.lstrip('@')}"
                    if await _send(
                        bot,
                        user.telegram_id,
                        FEEDBACK_10D,
                        event="feedback reminder 10d",
                        reply_markup=feedback_button(url),
                    ):
                        eng.feedback_10d_sent = True

                # free limit reminder
                if user.grade == "free":
                    if user.requests_used >= user.request_limit:
                        if eng.limit_reached_at is None:
                            eng.limit_reached_at = now
                    else:
                        eng.limit_reached_at = None
                        eng.limit_reminder_sent = False
                    if (
                        eng.limit_reached_at
                        and not eng.limit_reminder_sent
                        and now - eng.limit_reached_at >= timedelta(days=3)
                    ):
                        if await _send(
                            bot,
                            user.telegram_id,
                            FREE_LIMIT_PAY_REMINDER,
                            event="free limit reminder",
                            reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
                        ):
                            eng.limit_reminder_sent = True
                else:
                    eng.limit_reached_at = None
                    eng.limit_reminder_sent = False

                # inactivity reminders
                last_ts = user.last_request
                if last_ts:
                    days = (now - last_ts).days
                    if days >= 30 and not eng.inactivity_30d_sent:
                        if await _send(
                            bot,
                            user.telegram_id,
                            INACTIVE_30D,
                            event="inactive 30d",
                        ):
                            eng.inactivity_30d_sent = True
                    elif days >= 14 and not eng.inactivity_14d_sent:
                        if await _send(
                            bot,
                            user.telegram_id,
                            INACTIVE_14D,
                            event="inactive 14d",
                        ):
                            eng.inactivity_14d_sent = True
                    elif days >= 7 and not eng.inactivity_7d_sent:
                        if await _send(
                            bot,
                            user.telegram_id,
                            INACTIVE_7D,
                            event="inactive 7d",
                        ):
                            eng.inactivity_7d_sent = True

            session.commit()
            session.close()

            # pending meal reminders
            now_ts = time.time()
            for meal_id, meal in list(pending_meals.items()):
                ts = meal.get("timestamp")
                if ts and now_ts - ts > 1800 and not meal.get("reminded"):
                    chat_id = meal.get("chat_id")
                    msg_id = meal.get("message_id")
                    if await _send(
                        bot,
                        chat_id,
                        ADD_MEAL_REMINDER,
                        event="pending meal reminder",
                        reply_to_message_id=msg_id,
                    ):
                        meal["reminded"] = True

            await asyncio.sleep(check_interval)

    def _start(bot: Bot):
        return _watch(bot)

    return _start

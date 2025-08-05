import asyncio
import time
from datetime import datetime, timedelta
from aiogram import Bot

from .database import SessionLocal, User, RequestLog, Meal, EngagementStatus
from .keyboards import subscribe_button, feedback_button
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

    prev = (
        session.query(RequestLog.timestamp)
        .filter_by(user_id=user.id)
        .order_by(RequestLog.timestamp.desc())
        .offset(1)
        .first()
    )
    prev_ts = prev.timestamp if prev else None

    if not eng.first_request_sent and user.requests_total >= 1:
        try:
            await bot.send_message(user.telegram_id, FIRST_REQUEST_DONE)
        except Exception:
            pass
        eng.first_request_sent = True

    if not eng.three_requests_sent and user.requests_total >= 3:
        try:
            await bot.send_message(user.telegram_id, THREE_REQUESTS_DONE)
        except Exception:
            pass
        eng.three_requests_sent = True

    if not eng.seven_requests_sent and user.requests_total >= 7:
        try:
            await bot.send_message(user.telegram_id, SEVEN_REQUESTS_DONE)
        except Exception:
            pass
        eng.seven_requests_sent = True

    if (
        not eng.five_no_meal_sent
        and user.requests_total >= 5
        and session.query(Meal).filter_by(user_id=user.id).count() == 0
    ):
        try:
            await bot.send_message(user.telegram_id, NO_MEAL_AFTER_REQUESTS)
        except Exception:
            pass
        eng.five_no_meal_sent = True

    if prev_ts and now - prev_ts >= timedelta(days=7):
        try:
            await bot.send_message(user.telegram_id, WELCOME_BACK)
        except Exception:
            pass
    eng.inactivity_7d_sent = False
    eng.inactivity_14d_sent = False
    eng.inactivity_30d_sent = False

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
                        try:
                            await bot.send_message(user.telegram_id, WELCOME_REMINDER_15M)
                        except Exception:
                            pass
                        eng.no_request_15m = True
                    if (
                        not eng.no_request_24h
                        and delta >= timedelta(hours=24)
                    ):
                        try:
                            await bot.send_message(user.telegram_id, WELCOME_REMINDER_24H)
                        except Exception:
                            pass
                        eng.no_request_24h = True
                    if (
                        not eng.no_request_3d
                        and delta >= timedelta(days=3)
                    ):
                        try:
                            await bot.send_message(user.telegram_id, WELCOME_REMINDER_3D)
                        except Exception:
                            pass
                        eng.no_request_3d = True

                # 10-day feedback
                if (
                    not eng.feedback_10d_sent
                    and now - (user.created_at or now) >= timedelta(days=10)
                ):
                    url = f"https://t.me/{SUPPORT_HANDLE.lstrip('@')}"
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            FEEDBACK_10D,
                            reply_markup=feedback_button(url),
                        )
                    except Exception:
                        pass
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
                        try:
                            await bot.send_message(
                                user.telegram_id,
                                FREE_LIMIT_PAY_REMINDER,
                                reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
                            )
                        except Exception:
                            pass
                        eng.limit_reminder_sent = True
                else:
                    eng.limit_reached_at = None
                    eng.limit_reminder_sent = False

                # inactivity reminders
                last = (
                    session.query(RequestLog.timestamp)
                    .filter_by(user_id=user.id)
                    .order_by(RequestLog.timestamp.desc())
                    .first()
                )
                last_ts = last.timestamp if last else None
                if last_ts:
                    days = (now - last_ts).days
                    if days >= 30 and not eng.inactivity_30d_sent:
                        try:
                            await bot.send_message(user.telegram_id, INACTIVE_30D)
                        except Exception:
                            pass
                        eng.inactivity_30d_sent = True
                    elif days >= 14 and not eng.inactivity_14d_sent:
                        try:
                            await bot.send_message(user.telegram_id, INACTIVE_14D)
                        except Exception:
                            pass
                        eng.inactivity_14d_sent = True
                    elif days >= 7 and not eng.inactivity_7d_sent:
                        try:
                            await bot.send_message(user.telegram_id, INACTIVE_7D)
                        except Exception:
                            pass
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
                    try:
                        await bot.send_message(
                            chat_id,
                            ADD_MEAL_REMINDER,
                            reply_to_message_id=msg_id,
                        )
                    except Exception:
                        pass
                    meal["reminded"] = True

            await asyncio.sleep(check_interval)

    def _start(bot: Bot):
        return _watch(bot)

    return _start

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

import asyncio
from aiogram import Bot
from .keyboards import subscribe_button
from .texts import (
    SUB_END_7D,
    SUB_END_3D,
    SUB_END_1D,
    SUB_PAUSED,
    FREE_DAY_TEXT,
    BTN_RENEW_SUB,
    BTN_REMOVE_LIMIT,
)

from .database import SessionLocal, User, Payment

from .logger import log

FREE_LIMIT = 20
PAID_LIMIT = 800


def ensure_user(session: SessionLocal, telegram_id: int) -> User:
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        now = datetime.utcnow()
        user = User(
            telegram_id=telegram_id,
            grade="free",
            request_limit=FREE_LIMIT,
            requests_used=0,
            period_start=now,
            period_end=now + timedelta(days=30),
            notified_1d=False,
            notified_free=True,
            daily_used=0,
            daily_start=now,
        )
        session.add(user)
        session.commit()
    return user


def update_limits(user: User) -> None:
    now = datetime.utcnow()
    if user.period_start is None:
        user.period_start = now
    if user.daily_start is None:
        user.daily_start = now
        user.daily_used = 0
    elif now.date() != user.daily_start.date():
        user.daily_start = now
        user.daily_used = 0
    if user.grade in {"paid", "pro"}:
        if user.period_end and now > user.period_end:
            # subscription expired
            user.grade = "free"
            user.request_limit = FREE_LIMIT
            user.requests_used = 0
            user.period_start = now
            user.period_end = now + timedelta(days=30)
            user.notified_7d = False
            user.notified_3d = False
            user.notified_1d = False
            user.notified_0d = False
            user.notified_free = True
            log("notification", "subscription expired for %s", user.telegram_id)
    else:
        if user.period_end is None:
            user.period_end = user.period_start + timedelta(days=30)
        if now >= user.period_end:
            prev = user.requests_used
            user.period_start = now
            user.period_end = now + timedelta(days=30)
            user.requests_used = 0
            user.notified_free = prev == 0
            log("limit", "free requests renewed for %s", user.telegram_id)


def has_request_quota(session: SessionLocal, user: User) -> bool:
    """Check if user has remaining GPT requests without consuming one."""
    update_limits(user)
    session.commit()
    if user.grade in {"paid", "pro"} and user.daily_used >= 100:
        return False
    return user.requests_used < user.request_limit


def consume_request(session: SessionLocal, user: User) -> tuple[bool, str]:
    update_limits(user)
    if user.grade in {"paid", "pro"} and user.daily_used >= 100:
        log("limit", "daily limit reached for %s", user.telegram_id)
        return False, "daily"
    if user.requests_used >= user.request_limit:
        log("limit", "monthly limit reached for %s", user.telegram_id)
        return False, "monthly"
    user.requests_used += 1
    if user.grade in {"paid", "pro"}:
        user.daily_used += 1
    session.commit()
    log("limit", "request consumed by %s", user.telegram_id)
    return True, ""


def days_left(user: User) -> Optional[int]:
    if user.grade not in {"paid", "pro"} or not user.period_end:
        return None
    return (user.period_end.date() - datetime.utcnow().date()).days


def process_payment_success(
    session: SessionLocal, user: User, months: int = 1, grade: str = "paid"
):
    now = datetime.utcnow()

    def add_period(dt: datetime, count: int = 1) -> datetime:
        """Add count * 30 days to dt."""
        return dt + timedelta(days=30 * count)

    if user.grade in {"paid", "pro"} and user.period_end and user.period_end > now:
        user.period_end = add_period(user.period_end, months)
    else:
        user.period_end = add_period(now, months)
    user.grade = grade
    user.request_limit = PAID_LIMIT
    user.requests_used = 0
    user.notified_7d = False
    user.notified_3d = False
    user.notified_1d = False
    user.notified_0d = False
    payment = Payment(user_id=user.id, months=months, tier=grade)
    session.add(payment)
    session.commit()
    log("payment", "subscription purchased: %s for %s months", user.telegram_id, months)


def add_subscription_days(session: SessionLocal, user: User, days: int) -> None:
    """Extend user's subscription by given number of days."""
    if user.grade not in {"paid", "pro"}:
        return
    now = datetime.utcnow()
    if user.period_end and user.period_end > now:
        user.period_end += timedelta(days=days)
    else:
        user.period_end = now + timedelta(days=days)
    session.commit()


def subscription_watcher(bot: Bot, check_interval: int = 3600):
    """Check subscriptions periodically and notify users."""

    async def _watch():
        while True:
            await _daily_check(bot)
            await asyncio.sleep(check_interval)

    return _watch


async def _daily_check(bot: Bot):
    session = SessionLocal()
    now = datetime.utcnow()
    users = session.query(User).all()
    for user in users:
        if user.grade in {"paid", "pro"} and user.period_end:
            days = (user.period_end.date() - now.date()).days
            text = None
            if days <= 0 and not user.notified_0d:
                text = SUB_PAUSED
                user.notified_0d = True
            elif days == 1 and not user.notified_1d:
                text = SUB_END_1D
                user.notified_1d = True
            elif days == 3 and not user.notified_3d:
                text = SUB_END_3D
                user.notified_3d = True
            elif days == 7 and not user.notified_7d:
                text = SUB_END_7D
                user.notified_7d = True
            if text:
                kb = subscribe_button(BTN_RENEW_SUB)
                try:
                    await bot.send_message(user.telegram_id, text, reply_markup=kb)
                    log("notification", "sent subscription notice to %s", user.telegram_id)
                except Exception:
                    pass
        update_limits(user)
        if user.grade == "free" and not user.notified_free:
            try:
                await bot.send_message(
                    user.telegram_id,
                    FREE_DAY_TEXT,
                    reply_markup=subscribe_button(BTN_REMOVE_LIMIT),
                )
                user.notified_free = True
                log("notification", "sent free quota notice to %s", user.telegram_id)
            except Exception:
                pass
    session.commit()
    session.close()


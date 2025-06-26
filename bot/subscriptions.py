from __future__ import annotations
from datetime import datetime, timedelta
from calendar import monthrange
from typing import Optional

import asyncio
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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

from .database import SessionLocal, User

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
            notified_free=False,
        )
        session.add(user)
        session.commit()
    return user


def update_limits(user: User) -> None:
    now = datetime.utcnow()
    if user.period_start is None:
        user.period_start = now
    if user.grade == "paid":
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
    else:
        if user.period_end is None:
            user.period_end = user.period_start + timedelta(days=30)
        if now >= user.period_end:
            user.period_start = now
            user.period_end = now + timedelta(days=30)
            user.requests_used = 0
            user.notified_free = False


def has_request_quota(session: SessionLocal, user: User) -> bool:
    """Check if user has remaining GPT requests without consuming one."""
    update_limits(user)
    session.commit()
    return user.requests_used < user.request_limit


def consume_request(session: SessionLocal, user: User) -> bool:
    update_limits(user)
    if user.requests_used >= user.request_limit:
        return False
    user.requests_used += 1
    session.commit()
    return True


def days_left(user: User) -> Optional[int]:
    if user.grade != "paid" or not user.period_end:
        return None
    return (user.period_end.date() - datetime.utcnow().date()).days


def process_payment_success(session: SessionLocal, user: User, months: int = 1):
    now = datetime.utcnow()

    def add_month(dt: datetime, count: int = 1) -> datetime:
        month = dt.month + count
        year = dt.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(dt.day, monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)

    if user.grade == "paid" and user.period_end and user.period_end > now:
        user.period_end = add_month(user.period_end, months)
    else:
        user.period_end = add_month(now, months)
    user.grade = "paid"
    user.request_limit = PAID_LIMIT
    user.requests_used = 0
    user.notified_7d = False
    user.notified_3d = False
    user.notified_1d = False
    user.notified_0d = False
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
        if user.grade == "paid" and user.period_end:
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
            except Exception:
                pass
    session.commit()
    session.close()


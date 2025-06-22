from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

import asyncio
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .database import SessionLocal, User

FREE_LIMIT = 20
PAID_LIMIT = 800


def ensure_user(session: SessionLocal, telegram_id: int) -> User:
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            grade="free",
            request_limit=FREE_LIMIT,
            requests_used=0,
            period_start=datetime.utcnow(),
        )
        session.add(user)
        session.commit()
    return user


def update_limits(user: User) -> None:
    now = datetime.utcnow()
    if user.grade == "paid":
        if user.period_end and now > user.period_end:
            # subscription expired
            user.grade = "free"
            user.request_limit = FREE_LIMIT
            user.requests_used = 0
            user.period_start = now
            user.period_end = None
            user.notified_7d = False
            user.notified_3d = False
            user.notified_0d = False
    else:
        if now >= user.period_start + timedelta(days=30):
            user.period_start = now
            user.requests_used = 0


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


def process_payment_success(session: SessionLocal, user: User):
    now = datetime.utcnow()
    if user.period_end and user.period_end > now:
        user.period_end += timedelta(days=30)
    else:
        user.period_end = now + timedelta(days=30)
    user.grade = "paid"
    user.request_limit = PAID_LIMIT
    user.requests_used = 0
    user.notified_7d = False
    user.notified_3d = False
    user.notified_0d = False
    session.commit()


def subscription_watcher(bot: Bot, check_interval: int = 3600):
    async def _watch():
        last_date = None
        while True:
            now = datetime.utcnow() + timedelta(hours=3)  # Moscow time
            if last_date != now.date():
                last_date = now.date()
                await _daily_check(bot)
            await asyncio.sleep(check_interval)
    return _watch


async def _daily_check(bot: Bot):
    session = SessionLocal()
    now = datetime.utcnow()
    users = session.query(User).all()
    for user in users:
        update_limits(user)
        if user.grade == "paid" and user.period_end:
            days = (user.period_end.date() - now.date()).days
            text = None
            if days <= 0 and not user.notified_0d:
                text = "Твоя подписка закончилась"
                user.notified_0d = True
            elif days == 3 and not user.notified_3d:
                text = "Твоя подписка заканчивается через 3 дня"
                user.notified_3d = True
            elif days == 7 and not user.notified_7d:
                text = "Твоя подписка заканчивается через 7 дней"
                user.notified_7d = True
            if text:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Оплатить", callback_data="pay")]]
                )
                try:
                    await bot.send_message(user.telegram_id, text, reply_markup=kb)
                except Exception:
                    pass
    session.commit()
    session.close()


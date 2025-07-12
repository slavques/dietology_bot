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
    TRIAL_ENDED,
    TRIAL_PRO_ENDED_START,
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
    if user.trial and user.trial_end and now > user.trial_end:
        if user.resume_grade:
            user.grade = user.resume_grade
            user.period_end = user.resume_period_end
        else:
            user.grade = "free"
            user.request_limit = FREE_LIMIT
            user.requests_used = 0
            user.period_start = now
            user.period_end = now + timedelta(days=30)
            user.notified_free = True
        # keep trial flags until watcher sends notification
        log("notification", "trial expired for %s pending notice", user.telegram_id)
    elif user.grade in {"light", "pro"} and not user.trial:
        if user.period_end and now > user.period_end:
            if user.resume_grade:
                user.grade = user.resume_grade
                user.period_end = user.resume_period_end
                user.resume_grade = None
                user.resume_period_end = None
                log(
                    "notification",
                    "subscription resumed for %s",
                    user.telegram_id,
                )
            elif user.notified_0d:
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
                log(
                    "notification",
                    "subscription expired for %s",
                    user.telegram_id,
                )
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
    if user.grade in {"light", "pro"} and user.daily_used >= 100:
        return False
    return user.requests_used < user.request_limit


def consume_request(session: SessionLocal, user: User) -> tuple[bool, str]:
    update_limits(user)
    if user.grade in {"light", "pro"} and user.daily_used >= 100:
        log("limit", "daily limit reached for %s", user.telegram_id)
        return False, "daily"
    if user.requests_used >= user.request_limit:
        log("limit", "monthly limit reached for %s", user.telegram_id)
        return False, "monthly"
    user.requests_used += 1
    if user.grade in {"light", "pro"}:
        user.daily_used += 1
    session.commit()
    log("limit", "request consumed by %s", user.telegram_id)
    return True, ""


def days_left(user: User) -> Optional[int]:
    if user.trial and user.trial_end:
        return (user.trial_end.date() - datetime.utcnow().date()).days
    if user.grade not in {"light", "pro"} or not user.period_end:
        return None
    return (user.period_end.date() - datetime.utcnow().date()).days


def process_payment_success(
    session: SessionLocal, user: User, months: int = 1, grade: str = "light"
):
    now = datetime.utcnow()

    if user.trial:
        user.trial = False
        user.trial_end = None
        user.resume_grade = None
        user.resume_period_end = None

    def add_period(dt: datetime, count: int = 1) -> datetime:
        """Add count * 30 days to dt."""
        return dt + timedelta(days=30 * count)

    current_grade = user.grade

    if (
        current_grade == "light"
        and grade == "pro"
        and user.period_end
        and user.period_end > now
        and not user.resume_grade
    ):
        user.resume_grade = "light"
        user.resume_period_end = user.period_end

    if current_grade == grade and user.period_end and user.period_end > now:
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
    if user.grade not in {"light", "pro"} or user.trial:
        return
    now = datetime.utcnow()
    if user.period_end and user.period_end > now:
        user.period_end += timedelta(days=days)
    else:
        user.period_end = now + timedelta(days=days)
    session.commit()


def start_trial(session: SessionLocal, user: User, days: int, grade: str) -> None:
    """Start a trial subscription for the user."""
    now = datetime.utcnow()
    # Save current paid subscription if any
    if user.grade in {"light", "pro"} and not user.trial:
        user.resume_grade = user.grade
        user.resume_period_end = (user.period_end or now) + timedelta(days=days)
    else:
        user.resume_grade = None
        user.resume_period_end = None
    trial_grade = f"{grade}_promo"
    user.grade = trial_grade
    user.period_start = now
    user.trial_end = now + timedelta(days=days)
    user.request_limit = PAID_LIMIT
    user.requests_used = 0
    user.daily_used = 0
    user.daily_start = now
    user.trial = True
    user.trial_used = True
    user.notified_7d = False
    user.notified_3d = False
    user.notified_1d = False
    user.notified_0d = False
    session.commit()
    from .logger import log
    log("trial", "trial started for %s: %s days %s", user.telegram_id, days, grade)


def check_start_trial(session: SessionLocal, user: User) -> Optional[tuple[str, int]]:
    """Apply start trial to new users if enabled. Returns grade and days."""
    from .database import get_option_bool, get_option_int

    if user.trial_used:
        return None
    if get_option_bool("trial_pro_enabled", False):
        days = get_option_int("trial_pro_days", 0)
        if days > 0:
            start_trial(session, user, days, "pro")
            from .logger import log
            log("trial", "auto start trial pro for %s", user.telegram_id)
            return "pro", days
    if get_option_bool("trial_light_enabled", False):
        days = get_option_int("trial_light_days", 0)
        if days > 0:
            start_trial(session, user, days, "light")
            return "light", days
    return None


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
        update_limits(user)
        if user.trial and user.trial_end:
            t_days = (user.trial_end.date() - now.date()).days
            if t_days <= 0 and not user.notified_0d:
                try:
                    text = TRIAL_ENDED
                    if user.resume_grade == "light" and user.grade.startswith("pro"):
                        text = TRIAL_PRO_ENDED_START
                    await bot.send_message(
                        user.telegram_id,
                        text,
                        reply_markup=subscribe_button(BTN_REMOVE_LIMIT),
                    )
                    log("notification", "trial ended notice to %s", user.telegram_id)
                except Exception:
                    pass
                if user.resume_grade:
                    user.grade = user.resume_grade
                    user.period_end = user.resume_period_end
                else:
                    user.grade = "free"
                    user.request_limit = FREE_LIMIT
                    user.requests_used = 0
                    user.period_start = now
                    user.period_end = now + timedelta(days=30)
                    user.notified_free = True
                user.trial = False
                user.trial_end = None
                user.resume_grade = None
                user.resume_period_end = None
                user.notified_0d = True
        elif user.grade in {"light", "pro"} and user.period_end and not user.trial:
            days = (user.period_end.date() - now.date()).days
            text = None
            price = PLAN_PRICES["1m"] if user.grade == "light" else PRO_PLAN_PRICES["1m"]
            if days <= 0 and not user.notified_0d:
                text = SUB_PAUSED.format(price=price)
                user.notified_0d = True
            elif days == 1 and not user.notified_1d:
                text = SUB_END_1D.format(price=price)
                user.notified_1d = True
            elif days == 3 and not user.notified_3d:
                text = SUB_END_3D.format(price=price)
                user.notified_3d = True
            elif days == 7 and not user.notified_7d:
                text = SUB_END_7D.format(price=price)
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


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
    SUB_SWITCHED,
)
from .settings import PLAN_PRICES, PRO_PLAN_PRICES

from .database import (
    SessionLocal,
    User,
    Payment,
    Subscription,
    NotificationStatus,
    ReminderSettings,
    EngagementStatus,
)

from .logger import log
from .alerts import (
    anomalous_activity,
    user_blocked_daily,
    monthly_limit as alert_monthly_limit,
)

FREE_LIMIT = 20
PAID_LIMIT = 800


def update_monthly(user: User) -> None:
    """Reset monthly counters every 30 days since registration."""
    if user.monthly_start is None:
        user.monthly_start = user.created_at or datetime.utcnow()
        user.monthly_used = 0
    now = datetime.utcnow()
    while (now - user.monthly_start).days >= 30:
        user.monthly_start += timedelta(days=30)
        user.monthly_used = 0


def grade_name(grade: str) -> str:
    """Return user-facing name for a subscription grade."""
    return "⚡ Pro-режим" if grade.startswith("pro") else "🔸 Старт"


def ensure_user(session: SessionLocal, telegram_id: int) -> User:
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        now = datetime.utcnow()
        user = User(telegram_id=telegram_id)
        user.subscription = Subscription(
            grade="free",
            request_limit=FREE_LIMIT,
            requests_used=0,
            requests_total=0,
            monthly_used=0,
            monthly_start=now,
            period_start=now,
            period_end=now + timedelta(days=30),
            daily_used=0,
            daily_start=now,
        )
        user.notification = NotificationStatus(
            notified_1d=False,
            notified_free=True,
        )
        user.reminders = ReminderSettings()
        user.engagement = EngagementStatus()
        session.add(user)
        session.commit()
    return user


def update_limits(user: User) -> None:
    update_monthly(user)
    now = datetime.utcnow()
    if user.grade != "free":
        user.goal_trial_start = None
        user.goal_trial_notified = False
    if user.period_start is None:
        user.period_start = now
    if user.daily_start is None:
        user.daily_start = now
        user.daily_used = 0
    elif now.date() != user.daily_start.date():
        user.daily_start = now
        user.daily_used = 0
    if user.trial and user.trial_end and now > user.trial_end:
        # trial is over, but keep state intact so the watcher can notify the user
        # and restore their previous subscription properly
        log("notification", "trial expired for %s pending notice", user.telegram_id)
    elif user.grade in {"light", "pro"} and not user.trial:
        if user.period_end and now > user.period_end:
            if user.resume_grade:
                if user.resume_period_end and now <= user.resume_period_end:
                    user.grade = user.resume_grade
                    user.period_end = user.resume_period_end
                    user.resume_grade = None
                    user.resume_period_end = None
                    user.notified_0d = False
                    log(
                        "notification",
                        "subscription resumed for %s",
                        user.telegram_id,
                    )
                else:
                    user.resume_grade = None
                    user.resume_period_end = None
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
                user.goal_trial_start = now
                user.goal_trial_notified = False
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
            user.goal_trial_start = None
            user.goal_trial_notified = False
            log("limit", "free requests renewed for %s", user.telegram_id)


def has_request_quota(session: SessionLocal, user: User) -> bool:
    """Check if user has remaining GPT requests without consuming one."""
    update_limits(user)
    session.commit()
    if user.daily_used >= 100:
        return False
    return user.requests_used < user.request_limit


def consume_request(session: SessionLocal, user: User) -> tuple[bool, str]:
    update_limits(user)
    if user.daily_used >= 100:
        log("limit", "daily limit reached for %s", user.telegram_id)
        return False, "daily"
    if user.requests_used >= user.request_limit:
        log("limit", "monthly limit reached for %s", user.telegram_id)
        return False, "monthly"
    user.requests_used += 1
    user.monthly_used += 1
    user.requests_total += 1
    user.daily_used += 1
    if user.daily_used in {50, 100}:
        asyncio.create_task(anomalous_activity(user.telegram_id, user.daily_used))
    blocked = False
    if user.daily_used >= 100:
        user.blocked = True
        blocked = True
    if user.monthly_used == 800:
        asyncio.create_task(alert_monthly_limit(user.telegram_id))
    session.commit()
    if blocked:
        asyncio.create_task(user_blocked_daily(user.telegram_id))
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
    user.goal_trial_start = None
    user.goal_trial_notified = False
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


async def notify_trial_end(bot: Bot, session: SessionLocal, user: User) -> None:
    """Notify user about expired trial and restore subscription if needed."""
    now = datetime.utcnow()
    if (
        user.trial
        and user.trial_end
        and now > user.trial_end
        and not user.notified_0d
    ):
        text = TRIAL_ENDED
        if user.resume_grade == "light" and user.grade.startswith("pro"):
            text = TRIAL_PRO_ENDED_START
        try:
            kb = None if text == TRIAL_PRO_ENDED_START else subscribe_button(BTN_REMOVE_LIMIT)
            await bot.send_message(
                user.telegram_id,
                text,
                reply_markup=kb,
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
        # Don't mark the subscription as notified about expiry yet.
        # The user's previous plan may still be active after the trial ends,
        # so keep this flag clear to allow future expiry reminders.
        user.notified_0d = False
        session.commit()


def subscription_watcher(bot: Bot, check_interval: int = 3600):
    """Check subscriptions periodically and notify users."""

    async def _watch():
        log("watcher", "subscription watcher started with %s sec interval", check_interval)
        while True:
            await _daily_check(bot)
            await asyncio.sleep(check_interval)

    return _watch


async def _daily_check(bot: Bot):
    log("watcher", "running subscription check")
    session = SessionLocal()
    now = datetime.utcnow()
    users = session.query(User).all()
    for user in users:
        await notify_trial_end(bot, session, user)
        if (
            user.grade in {"light", "pro"}
            and user.period_end
            and now > user.period_end
            and user.resume_grade
            and user.resume_period_end
            and user.resume_period_end > now
            and not user.trial
        ):
            if not user.notified_0d:
                text = SUB_SWITCHED.format(
                    old=grade_name(user.grade),
                    new=grade_name(user.resume_grade),
                )
                try:
                    await bot.send_message(user.telegram_id, text)
                    log(
                        "notification",
                        "sent plan switch notice to %s",
                        user.telegram_id,
                    )
                except Exception:
                    pass
            user.grade = user.resume_grade
            user.period_end = user.resume_period_end
            user.resume_grade = None
            user.resume_period_end = None
            user.notified_0d = False
            session.commit()
            continue
        if (
            user.resume_grade
            and user.resume_period_end
            and now > user.resume_period_end
            and user.grade in {"light", "pro"}
            and not user.trial
            and user.period_end
            and now <= user.period_end
        ):
            if not user.notified_0d:
                text = SUB_SWITCHED.format(
                    old=grade_name(user.resume_grade),
                    new=grade_name(user.grade),
                )
                try:
                    await bot.send_message(user.telegram_id, text)
                    log(
                        "notification",
                        "sent plan switch notice to %s",
                        user.telegram_id,
                    )
                except Exception:
                    pass
                user.notified_0d = True
        if user.grade in {"light", "pro"} and user.period_end and not user.trial:
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


import asyncio
import random
import re
from datetime import datetime, timedelta, time
from html import escape

from aiogram import Bot

from .database import SessionLocal, User, Meal
from .keyboards import subscribe_button
from .logger import log
from .messaging import send_with_retries
from .texts import (
    REM_TEXT_MORNING,
    REM_TEXT_DAY,
    REM_TEXT_EVENING,
    GOAL_REMINDERS_DISABLED,
    GOAL_TRIAL_EXPIRED_NOTICE,
    BTN_REMOVE_LIMITS,
)
from .alerts import token_monitor
from .services import _chat_completion
from .prompts import GOAL_REMINDER_MORNING_PROMPT, GOAL_REMINDER_EVENING_PROMPT

TARGET_MAP = {"loss": "похудение", "gain": "набор", "maintain": "поддержка"}


def _meal_stats(meals):
    calories = protein = fat = carbs = 0
    names = []
    for m in meals:
        calories += float(m.calories or 0)
        protein += float(m.protein or 0)
        fat += float(m.fat or 0)
        carbs += float(m.carbs or 0)
        if m.name:
            names.append(m.name)
    return calories, protein, fat, carbs, names


def _day_bounds(local_now: datetime, offset: timedelta, days: int = 0):
    local_date = (local_now + timedelta(days=days)).date()
    start_local = datetime.combine(local_date, time())
    start_utc = start_local - offset
    end_utc = start_utc + timedelta(days=1)
    return start_utc, end_utc


def _parse_time(value: str) -> time:
    try:
        h, m = map(int, value.split(":", 1))
        return time(hour=h, minute=m)
    except Exception:
        return time(hour=0, minute=0)


def _format_macro(value) -> str:
    try:
        num = round(float(value), 1)
    except (TypeError, ValueError):
        return "0"
    if num == int(num):
        return str(int(num))
    return f"{num:.1f}".rstrip("0").rstrip(".")


def _highlight_numbers(text: str) -> str:
    return re.sub(r"(\d+(?:[.,]\d+)?)", r"<b>\1</b>", text)


def _format_gpt_message(content: str, message_type: str) -> tuple[str, bool]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content.strip()) if p.strip()]
    if not paragraphs:
        return escape(content.strip()), False

    if len(paragraphs) == 1:
        return escape(paragraphs[0]), False

    prefixes = {
        "morning": ("🌅 ", "📊 ", "💪 "),
        "evening": ("🌙 ", "📊 ", "💡 "),
    }
    default_prefix = ("", "📊 ", "💡 ")
    first_prefix, second_prefix, third_prefix = prefixes.get(message_type, default_prefix)

    formatted = []
    uses_markup = False
    for idx, paragraph in enumerate(paragraphs):
        escaped = escape(paragraph)
        if idx == 0:
            if escaped:
                escaped = f"{first_prefix}<b>{escaped}</b>"
                uses_markup = True
        else:
            escaped = _highlight_numbers(escaped)
            if "<b>" in escaped:
                uses_markup = True
            prefix = third_prefix if idx >= 2 else second_prefix
            escaped = f"{prefix}{escaped}" if escaped else ""
        formatted.append(escaped)
    return "\n\n".join(formatted), uses_markup


async def _send(
    bot: Bot,
    user: User,
    text: str,
    *,
    reply_markup=None,
    parse_mode=None,
    event: str | None = None,
) -> bool:
    """Deliver a reminder with retry logic and structured logging."""

    send_kwargs = {}
    if reply_markup is not None:
        send_kwargs["reply_markup"] = reply_markup
    if parse_mode:
        send_kwargs["parse_mode"] = parse_mode
    delivered = await send_with_retries(
        bot,
        user.telegram_id,
        text=text,
        category="notification",
        **send_kwargs,
    )
    label = event or text
    if delivered:
        log("notification", "sent reminder to %s: %s", user.telegram_id, label)
    else:
        log("notification", "failed to send reminder to %s: %s", user.telegram_id, label)
    return delivered


def reminder_watcher(check_interval: int = 60):
    async def _watch(bot: Bot):
        while True:
            now = datetime.utcnow()
            session = SessionLocal()
            from .database import ReminderSettings

            users = (
                session.query(User)
                .join(ReminderSettings)
                .filter(ReminderSettings.timezone != None)
                .all()
            )
            processed_user_ids = set()
            for user in users:
                processed_user_ids.add(user.id)
                offset = timedelta(minutes=user.timezone or 0)
                local_now = now + offset

                goal = getattr(user, "goal", None)
                if user.grade != "free":
                    if user.goal_trial_start or user.goal_trial_notified:
                        user.goal_trial_start = None
                        user.goal_trial_notified = False
                else:
                    start = getattr(user, "goal_trial_start", None)
                    expired = False
                    if start:
                        try:
                            expired = now >= start + timedelta(days=3)
                        except TypeError:
                            expired = False
                    if expired:
                        if goal:
                            session.delete(goal)
                        if not user.goal_trial_notified:
                            await _send(
                                bot,
                                user,
                                GOAL_TRIAL_EXPIRED_NOTICE,
                                reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
                            )
                        user.goal_trial_notified = True
                        continue
                if goal:
                    last_meal = (
                        session.query(Meal)
                        .filter(Meal.user_id == user.id)
                        .order_by(Meal.timestamp.desc())
                        .first()
                    )
                    if last_meal and last_meal.timestamp < now - timedelta(days=3):
                        session.delete(goal)
                        log(
                            "notification",
                            "goal reminders auto-disabled for %s",
                            user.telegram_id,
                        )
                        if user.grade != "free":
                            await _send(bot, user, GOAL_REMINDERS_DISABLED, reply_markup=None)
                        continue

                if goal and goal.reminder_morning and user.morning_time:
                    target = _parse_time(user.morning_time)
                    if (
                        (user.last_morning is None or user.last_morning.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        start, end = _day_bounds(local_now, offset, days=-1)
                        meals = (
                            session.query(Meal)
                            .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
                            .all()
                        )
                        cal, prot, fat, carb, _ = _meal_stats(meals)
                        prompt = GOAL_REMINDER_MORNING_PROMPT.format(
                            goal=TARGET_MAP.get(goal.target, goal.target),
                            plan_kcal=_format_macro(goal.calories),
                            plan_P=_format_macro(goal.protein),
                            plan_F=_format_macro(goal.fat),
                            plan_C=_format_macro(goal.carbs),
                            yday_kcal=_format_macro(cal),
                            yday_P=_format_macro(prot),
                            yday_F=_format_macro(fat),
                            yday_C=_format_macro(carb),
                        )
                        log("notification", "morning prompt for %s: %s", user.telegram_id, prompt)
                        content, tokens_in, tokens_out = await _chat_completion([
                            {"role": "user", "content": prompt}
                        ])
                        log("notification", "morning GPT response for %s: %s", user.telegram_id, content.strip())
                        await token_monitor.add(tokens_in, tokens_out)
                        formatted, use_html = _format_gpt_message(content.strip(), "morning")
                        await _send(
                            bot,
                            user,
                            formatted,
                            parse_mode="HTML" if use_html else None,
                            event="goal morning reminder",
                        )
                        user.last_morning = local_now
                elif user.morning_enabled and user.morning_time:
                    target = _parse_time(user.morning_time)
                    if (
                        (user.last_morning is None or user.last_morning.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        await _send(
                            bot,
                            user,
                            random.choice(REM_TEXT_MORNING),
                            event="morning reminder",
                        )
                        user.last_morning = local_now

                if user.day_enabled and user.day_time:
                    target = _parse_time(user.day_time)
                    if (
                        (user.last_day is None or user.last_day.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        await _send(
                            bot,
                            user,
                            random.choice(REM_TEXT_DAY),
                            event="day reminder",
                        )
                        user.last_day = local_now

                if goal and goal.reminder_evening and user.evening_time:
                    target = _parse_time(user.evening_time)
                    if (
                        (user.last_evening is None or user.last_evening.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        start, end = _day_bounds(local_now, offset, days=0)
                        meals = (
                            session.query(Meal)
                            .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
                            .all()
                        )
                        cal, prot, fat, carb, names = _meal_stats(meals)
                        names_str = ", ".join(names) if names else ""
                        prompt = GOAL_REMINDER_EVENING_PROMPT.format(
                            goal=TARGET_MAP.get(goal.target, goal.target),
                            plan_kcal=_format_macro(goal.calories),
                            plan_P=_format_macro(goal.protein),
                            plan_F=_format_macro(goal.fat),
                            plan_C=_format_macro(goal.carbs),
                            kcal=_format_macro(cal),
                            P=_format_macro(prot),
                            F=_format_macro(fat),
                            C=_format_macro(carb),
                            meals_list=names_str,
                        )
                        log("notification", "evening prompt for %s: %s", user.telegram_id, prompt)
                        content, tokens_in, tokens_out = await _chat_completion([
                            {"role": "user", "content": prompt}
                        ])
                        log("notification", "evening GPT response for %s: %s", user.telegram_id, content.strip())
                        await token_monitor.add(tokens_in, tokens_out)
                        formatted, use_html = _format_gpt_message(content.strip(), "evening")
                        await _send(
                            bot,
                            user,
                            formatted,
                            parse_mode="HTML" if use_html else None,
                            event="goal evening reminder",
                        )
                        user.last_evening = local_now
                elif user.evening_enabled and user.evening_time:
                    target = _parse_time(user.evening_time)
                    if (
                        (user.last_evening is None or user.last_evening.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        await _send(
                            bot,
                            user,
                            random.choice(REM_TEXT_EVENING),
                            event="evening reminder",
                        )
                        user.last_evening = local_now

            extra_users = (
                session.query(User)
                .filter(User.goal_trial_start != None)
                .all()
            )
            for user in extra_users:
                if user.id in processed_user_ids:
                    continue
                if user.grade != "free":
                    if user.goal_trial_start or user.goal_trial_notified:
                        user.goal_trial_start = None
                        user.goal_trial_notified = False
                    continue
                start = getattr(user, "goal_trial_start", None)
                if start and now >= start + timedelta(days=3):
                    goal = getattr(user, "goal", None)
                    if goal:
                        session.delete(goal)
                    if not user.goal_trial_notified:
                        await _send(
                            bot,
                            user,
                            GOAL_TRIAL_EXPIRED_NOTICE,
                            reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
                            event="goal trial expired notice",
                        )
                    user.goal_trial_notified = True
            session.commit()
            session.close()
            await asyncio.sleep(check_interval)
    def _start(bot: Bot):
        return _watch(bot)
    return _start

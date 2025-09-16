import asyncio
import random
from datetime import datetime, timedelta, time
from aiogram import Bot

from .database import SessionLocal, User, Meal
from .keyboards import subscribe_button
from .logger import log
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
        calories += m.calories or 0
        protein += m.protein or 0
        fat += m.fat or 0
        carbs += m.carbs or 0
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


async def _send(bot: Bot, user: User, text: str, reply_markup=None) -> None:
    try:
        await bot.send_message(user.telegram_id, text, reply_markup=reply_markup)
        log("notification", "sent reminder to %s: %s", user.telegram_id, text)
    except Exception:
        pass


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
            for user in users:
                offset = timedelta(minutes=user.timezone or 0)
                local_now = now + offset

                goal = getattr(user, "goal", None)
                if user.grade != "free":
                    if user.goal_trial_start or user.goal_trial_notified:
                        user.goal_trial_start = None
                        user.goal_trial_notified = False
                else:
                    start = getattr(user, "goal_trial_start", None)
                    if start and now >= start + timedelta(days=3):
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
                        await _send(bot, user, GOAL_REMINDERS_DISABLED)
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
                            plan_kcal=goal.calories,
                            plan_P=goal.protein,
                            plan_F=goal.fat,
                            plan_C=goal.carbs,
                            yday_kcal=int(cal),
                            yday_P=int(prot),
                            yday_F=int(fat),
                            yday_C=int(carb),
                        )
                        log("notification", "morning prompt for %s: %s", user.telegram_id, prompt)
                        content, tokens_in, tokens_out = await _chat_completion([
                            {"role": "user", "content": prompt}
                        ])
                        log("notification", "morning GPT response for %s: %s", user.telegram_id, content.strip())
                        await token_monitor.add(tokens_in, tokens_out)
                        await _send(bot, user, content.strip())
                        user.last_morning = local_now
                elif user.morning_enabled and user.morning_time:
                    target = _parse_time(user.morning_time)
                    if (
                        (user.last_morning is None or user.last_morning.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        await _send(bot, user, random.choice(REM_TEXT_MORNING))
                        user.last_morning = local_now

                if user.day_enabled and user.day_time:
                    target = _parse_time(user.day_time)
                    if (
                        (user.last_day is None or user.last_day.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        await _send(bot, user, random.choice(REM_TEXT_DAY))
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
                            plan_kcal=goal.calories,
                            plan_P=goal.protein,
                            plan_F=goal.fat,
                            plan_C=goal.carbs,
                            kcal=int(cal),
                            P=int(prot),
                            F=int(fat),
                            C=int(carb),
                            meals_list=names_str,
                        )
                        log("notification", "evening prompt for %s: %s", user.telegram_id, prompt)
                        content, tokens_in, tokens_out = await _chat_completion([
                            {"role": "user", "content": prompt}
                        ])
                        log("notification", "evening GPT response for %s: %s", user.telegram_id, content.strip())
                        await token_monitor.add(tokens_in, tokens_out)
                        await _send(bot, user, content.strip())
                        user.last_evening = local_now
                elif user.evening_enabled and user.evening_time:
                    target = _parse_time(user.evening_time)
                    if (
                        (user.last_evening is None or user.last_evening.date() != local_now.date())
                        and local_now.time().hour == target.hour
                        and local_now.time().minute == target.minute
                    ):
                        await _send(bot, user, random.choice(REM_TEXT_EVENING))
                        user.last_evening = local_now
            session.commit()
            session.close()
            await asyncio.sleep(check_interval)
    def _start(bot: Bot):
        return _watch(bot)
    return _start

from typing import Dict, Any, Optional
import re

from datetime import datetime, timedelta
from sqlalchemy import func

from .texts import MEAL_TEMPLATE
from .logger import log
from .database import SessionLocal, User, Meal


def format_meal_message(
    name: str, serving: float, macros: Dict[str, float], user_id: Optional[int] = None
) -> str:
    """Format meal info using the new template.

    If ``user_id`` is provided and the user has an active goal, a warning is
    appended when the given meal would push the user over the daily goal.
    """
    log("utils", f"Formatting meal message for {name}")
    message = MEAL_TEMPLATE.format(
        name=name,
        serving=serving,
        calories=macros["calories"],
        protein=macros["protein"],
        fat=macros["fat"],
        carbs=macros["carbs"],
    )

    if user_id is not None:
        session = SessionLocal()
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if user and user.goal and user.goal.calories:
            start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            totals = session.query(
                func.coalesce(func.sum(Meal.calories), 0),
                func.coalesce(func.sum(Meal.protein), 0),
                func.coalesce(func.sum(Meal.fat), 0),
                func.coalesce(func.sum(Meal.carbs), 0),
            ).filter(
                Meal.user_id == user.id,
                Meal.timestamp >= start,
                Meal.timestamp < end,
            ).one()
            cal_forecast = totals[0] + macros["calories"]
            p_forecast = totals[1] + macros["protein"]
            f_forecast = totals[2] + macros["fat"]
            c_forecast = totals[3] + macros["carbs"]
            cal_ex = max(0, round(cal_forecast - (user.goal.calories or 0), 1))
            p_ex = max(0, round(p_forecast - (user.goal.protein or 0), 1))
            f_ex = max(0, round(f_forecast - (user.goal.fat or 0), 1))
            c_ex = max(0, round(c_forecast - (user.goal.carbs or 0), 1))
            if cal_ex or p_ex or f_ex or c_ex:
                message += (
                    "\n\n"
                    f"⚠️ Добавив это блюдо, ты превысишь дневную цель на "
                    f"{int(cal_ex)} ккал и {int(p_ex)} б, {int(f_ex)} ж, {int(c_ex)} у"
                )
        session.close()
    log("utils", f"Formatted meal message: {message}")
    return message


def to_float(value: Any) -> float:
    """Convert value with possible units to float."""
    log("utils", f"Converting to float: {value}")
    if isinstance(value, (int, float)):
        result = float(value)
        log("utils", f"Converted result: {result}")
        return result
    match = re.search(r"(\d+(?:[\.,]\d+)?)", str(value))
    if match:
        result = float(match.group(1).replace(',', '.'))
        log("utils", f"Converted result: {result}")
        return result
    log("utils", "No numeric value found; returning 0.0")
    return 0.0


def parse_serving(value: Any) -> float:
    """Parse serving size from arbitrary value in grams rounded to 0.1."""
    log("utils", f"Parsing serving size from {value}")
    result = round(to_float(value), 1)
    log("utils", f"Parsed serving size: {result}")
    return result


def make_bar_chart(totals: Dict[str, float]) -> str:
    log("utils", f"Generating bar chart from totals: {totals}")
    max_val = max(totals.values()) if totals else 1
    bars = []
    for key, val in totals.items():
        bar = '█' * int((val / max_val) * 10)
        bars.append(f"{key[:1].upper()}: {bar} {val}")
    chart = "\n".join(bars)
    log("utils", f"Generated bar chart:\n{chart}")
    return chart


def plural_ru_day(days: int) -> str:
    """Return correct Russian declension for "день"."""
    log("utils", f"Pluralizing day for {days}")
    days = abs(int(days))
    if 11 <= days % 100 <= 14:
        word = "дней"
    else:
        last = days % 10
        if last == 1:
            word = "день"
        elif 2 <= last <= 4:
            word = "дня"
        else:
            word = "дней"
    log("utils", f"Plural result: {word}")
    return word

from typing import Dict, Any, Optional
import asyncio
import re

from datetime import datetime, timedelta, time
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
        with SessionLocal() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if user and user.goal and user.goal.calories:
                start = datetime.utcnow().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
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
                aggregated = dict(
                    zip(
                        ("calories", "protein", "fat", "carbs"),
                        totals,
                    )
                )
                overflow = {
                    key: max(
                        0,
                        round(
                            aggregated[key]
                            + macros[key]
                            - (getattr(user.goal, key, 0) or 0),
                            1,
                        ),
                    )
                    for key in ("calories", "protein", "fat", "carbs")
                }
                if any(overflow.values()):
                    message += (
                        "\n\n"
                        "⚠️ Добавив это блюдо, ты превысишь дневную цель на "
                        f"{int(overflow['calories'])} ккал и "
                        f"{int(overflow['protein'])} б, "
                        f"{int(overflow['fat'])} ж, {int(overflow['carbs'])} у"
                    )
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


def seconds_until_next_utc_midnight(now: Optional[datetime] = None) -> float:
    """Return seconds remaining until the next UTC midnight."""

    current = now or datetime.utcnow()
    tomorrow = current.date() + timedelta(days=1)
    midnight = datetime.combine(tomorrow, time())
    return max((midnight - current).total_seconds(), 0.0)


async def sleep_until_next_utc_midnight(now: Optional[datetime] = None) -> None:
    """Sleep asynchronously until the next UTC midnight."""

    await asyncio.sleep(seconds_until_next_utc_midnight(now))

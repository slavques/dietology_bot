from typing import Dict, Any
import re

from .texts import MEAL_TEMPLATE
from .logger import log


def format_meal_message(
    name: str, serving: float, macros: Dict[str, float]
) -> str:
    """Format meal info using the new template."""
    log("utils", f"Formatting meal message for {name}")
    message = MEAL_TEMPLATE.format(
        name=name,
        serving=serving,
        calories=macros["calories"],
        protein=macros["protein"],
        fat=macros["fat"],
        carbs=macros["carbs"],
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

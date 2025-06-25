from typing import Dict, Any
import re

def format_meal_message(name: str, serving: float, macros: Dict[str, float]) -> str:
    """Format meal info using the new template."""
    return (
        f"🍽 {name}\n"
        f"⚖ Вес: {serving} г\n"
        f"🔥 Калории: {macros['calories']} ккал\n"
        f"Белки: {macros['protein']} г\n"
        f"Жиры: {macros['fat']} г\n"
        f"Углеводы: {macros['carbs']} г"
    )


def to_float(value: Any) -> float:
    """Convert value with possible units to float."""
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"(\d+(?:[\.,]\d+)?)", str(value))
    if match:
        return float(match.group(1).replace(',', '.'))
    return 0.0


def parse_serving(value: Any) -> int:
    """Parse serving size from arbitrary value in grams."""
    return int(round(to_float(value)))

def make_bar_chart(totals: Dict[str, float]) -> str:
    max_val = max(totals.values()) if totals else 1
    chart = ""
    for key, val in totals.items():

        bar = '█' * int((val / max_val) * 10)
        chart += f"{key[:1].upper()}: {bar} {val}\n"
    return chart
DRINK_KEYWORDS = [
    "кофе", "капучино", "латте", "эспрессо", "мокко", "раф",
    "чай", "матча", "каркаде", "имбирный чай",
    "сок", "кола", "спрайт", "фанта", "pepси", "газировка",
    "вода", "бутылка", "бокал", "стакан", "кружка",
    "компот", "морс", "лимонад",
    "квас", "сидр", "шампанское",
    "молоко", "кефир", "айран",
    "коктейль", "молочный коктейль", "протеиновый коктейль",
    "энергетик", "изотоник",
    "пиво", "вино", "виски", "водка", "коньяк", "ром", "джин", "текила", "мохито",
    "какао", "смузи", "чашка"
]

def is_drink(name: str) -> bool:
    low = name.lower()
    return any(word in low for word in DRINK_KEYWORDS)


from typing import Dict

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

def make_bar_chart(totals: Dict[str, float]) -> str:
    max_val = max(totals.values()) if totals else 1
    chart = ""
    for key, val in totals.items():
        bar = '█' * int((val / max_val) * 10)
        chart += f"{key[:1].upper()}: {bar} {val}\n"
    return chart

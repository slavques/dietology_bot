from typing import Dict


def format_meal_message(name: str, serving: float, macros: Dict[str, float]) -> str:
    return (
        f"\U0001F37D {name}\n"
        f"\u2696 {serving} г\n"
        f"\U0001F522 {macros['calories']} ккал / {macros['protein']} г / {macros['fat']} г / {macros['carbs']} г"
    )


def make_bar_chart(totals: Dict[str, float]) -> str:
    max_val = max(totals.values()) if totals else 1
    chart = ""
    for key, val in totals.items():
        bar = '█' * int((val / max_val) * 10)
        chart += f"{key[:1].upper()}: {bar} {val}\n"
    return chart

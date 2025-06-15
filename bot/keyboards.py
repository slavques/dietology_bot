from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def meal_actions_kb(meal_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("Редактировать", callback_data=f"edit:{meal_id}"),
        InlineKeyboardButton("Удалить", callback_data=f"delete:{meal_id}"),
        InlineKeyboardButton("В историю", callback_data=f"save:{meal_id}"),
    )
    return markup


def history_nav_kb(offset: int, total: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    if offset > 0:
        markup.insert(InlineKeyboardButton("\u2190", callback_data=f"hist:{offset-1}"))
    if offset < total - 1:
        markup.insert(InlineKeyboardButton("\u2192", callback_data=f"hist:{offset+1}"))
    return markup


def stats_period_kb() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("День", callback_data="stats:day"),
        InlineKeyboardButton("Неделя", callback_data="stats:week"),
        InlineKeyboardButton("Месяц", callback_data="stats:month"),
    )
    return markup

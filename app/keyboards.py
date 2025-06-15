from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def meal_actions_keyboard(meal_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("Редактировать", callback_data=f"edit:{meal_id}"),
        InlineKeyboardButton("Удалить", callback_data=f"delete:{meal_id}"),
        InlineKeyboardButton("В историю", callback_data=f"save:{meal_id}"),
    )
    return markup


def period_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("День", callback_data="stats:day"),
        InlineKeyboardButton("Неделя", callback_data="stats:week"),
        InlineKeyboardButton("Месяц", callback_data="stats:month"),
    )
    return markup

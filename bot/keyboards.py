from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def meal_actions_kb(meal_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Редактировать", callback_data=f"edit:{meal_id}")
    builder.button(text="Удалить", callback_data=f"delete:{meal_id}")
    builder.button(text="В историю", callback_data=f"save:{meal_id}")
    builder.adjust(3)
    return builder.as_markup()


def history_nav_kb(offset: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.button(text="\u2190", callback_data=f"hist:{offset-1}")
    if offset < total - 1:
        builder.button(text="\u2192", callback_data=f"hist:{offset+1}")
    if builder.buttons:
        builder.adjust(len(builder.buttons))
    return builder.as_markup()


def stats_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="День", callback_data="stats:day")
    builder.button(text="Неделя", callback_data="stats:week")
    builder.button(text="Месяц", callback_data="stats:month")
    builder.adjust(3)
    return builder.as_markup()
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

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


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="\U0001F4F8 Новое фото"),
                KeyboardButton(text="\U0001F9FE \u041E\u0442\u0447\u0451\u0442 \u0437\u0430 \u0434\u0435\u043D\u044C"),
            ],
            [
                KeyboardButton(text="\U0001F4CA \u041C\u043E\u0438 \u043F\u0440\u0438\u0451\u043C\u044B"),
                KeyboardButton(text="\u2753 \u0427\u0430\u0412\u041E"),
            ],
        ],
        resize_keyboard=True,
    )
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def meal_actions_kb(meal_id: str, clarifications: int = 0) -> InlineKeyboardMarkup:
    """Inline keyboard for meal actions. Hide refine after two clarifications."""
    builder = InlineKeyboardBuilder()
    if clarifications < 2:
        builder.button(text="✏️ Уточнить", callback_data=f"edit:{meal_id}")
    builder.button(text="🗑 Удалить", callback_data=f"delete:{meal_id}")
    builder.button(text="💾 Сохранить", callback_data=f"save:{meal_id}")
    if clarifications < 2:
        builder.adjust(3)
    else:
        builder.adjust(2)
    return builder.as_markup()


def save_options_kb(meal_id: str) -> InlineKeyboardMarkup:
    """Keyboard with portion save options."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Вся порция", callback_data=f"full:{meal_id}")
    builder.button(text="1/2 Порции", callback_data=f"half:{meal_id}")
    builder.button(text="Назад", callback_data=f"back:{meal_id}")
    builder.adjust(1)
    return builder.as_markup()


def history_nav_kb(offset: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    count = 0
    if offset > 0:
        builder.button(text="\u2190", callback_data=f"hist:{offset-1}")
        count += 1
    if offset < total - 1:
        builder.button(text="\u2192", callback_data=f"hist:{offset+1}")
        count += 1
    if count:
        builder.adjust(count)
    return builder.as_markup()


def stats_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="День", callback_data="stats:day")
    builder.button(text="Неделя", callback_data="stats:week")
    builder.button(text="Месяц", callback_data="stats:month")
    builder.adjust(3)
    return builder.as_markup()


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Main menu with four actions arranged vertically."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\U0001F4F8 Новое фото")],
            [KeyboardButton(text="\U0001F9FE \u041E\u0442\u0447\u0451\u0442 \u0437\u0430 \u0434\u0435\u043D\u044C")],
            [KeyboardButton(text="\U0001F4CA \u041C\u043E\u0438 \u043F\u0440\u0438\u0451\u043C\u044B")],
            [KeyboardButton(text="\u2753 \u0427\u0430\u0412\u041E")],
        ],
        resize_keyboard=True,
    )


def back_menu_kb() -> ReplyKeyboardMarkup:
    """Keyboard with a single button to return to the main menu."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="\U0001F951 \u0413\u043B\u0430\u0432\u043D\u043E\u0435 \u043C\u0435\u043D\u044E")]],
        resize_keyboard=True,
    )

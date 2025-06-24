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
    builder.button(text="Полная порция", callback_data=f"full:{meal_id}")
    builder.button(text="Половина порции", callback_data=f"half:{meal_id}")
    builder.button(text="1/4 порции", callback_data=f"quarter:{meal_id}")
    builder.button(text="3/4 порции", callback_data=f"threeq:{meal_id}")
    builder.button(text="Назад", callback_data=f"back:{meal_id}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_save_kb(meal_id: str) -> InlineKeyboardMarkup:
    """Keyboard asking to confirm addition."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить", callback_data=f"add:{meal_id}")
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
            [KeyboardButton(text="🧾 Отчёт за день")],
            [KeyboardButton(text="📊 Мои приёмы")],
            [KeyboardButton(text="❓ ЧаВО")],
            [KeyboardButton(text="⚡ Подписка")],
        ],
        resize_keyboard=True,
    )


def back_menu_kb() -> ReplyKeyboardMarkup:
    """Keyboard with a single button to return to the main menu."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🥑 Главное меню")]],
        resize_keyboard=True,
    )


def pay_kb() -> InlineKeyboardMarkup:
    """Inline keyboard with a single payment button."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить", callback_data="pay")
    builder.adjust(1)
    return builder.as_markup()


def subscription_plans_kb() -> ReplyKeyboardMarkup:
    """Keyboard with subscription duration options."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚶‍♂️1 месяц - 149₽")],
            [KeyboardButton(text="🏃‍♂️3 месяца - 399₽")],
            [KeyboardButton(text="🧘‍♂️6 месяцев - 799₽")],
            [KeyboardButton(text="🥑 Главное меню")],
        ],
        resize_keyboard=True,
    )


def payment_methods_kb() -> ReplyKeyboardMarkup:
    """Keyboard with payment method choices."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Банковская карта")],
            [KeyboardButton(text="✨Telegram Stars")],
            [KeyboardButton(text="🪙Crypto")],
            [KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True,
    )


def subscribe_button(text: str) -> InlineKeyboardMarkup:
    """Inline keyboard leading to the subscription menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data="subscribe")
    builder.adjust(1)
    return builder.as_markup()

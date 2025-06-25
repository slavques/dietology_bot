from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from .settings import PLAN_PRICES
from typing import Optional
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
            [KeyboardButton(text="⚡ Подписка")],
            [KeyboardButton(text="❓ ЧаВО")],
        ],
        resize_keyboard=True,
    )


def back_menu_kb() -> ReplyKeyboardMarkup:
    """Keyboard with a single button to return to the main menu."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🥑 Главное меню")]],
        resize_keyboard=True,
    )


def pay_kb(code: Optional[str] = None) -> InlineKeyboardMarkup:
    """Inline keyboard with a single payment button.

    Optionally encodes the selected plan in callback data so invoice
    handlers can determine which subscription to bill for.
    """
    builder = InlineKeyboardBuilder()
    cb = f"pay:{code}" if code else "pay"
    builder.button(text="Оплатить", callback_data=cb)
    builder.adjust(1)
    return builder.as_markup()


def subscription_plans_kb() -> ReplyKeyboardMarkup:
    """Keyboard with subscription duration options."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"🚶‍♂️1 месяц - {PLAN_PRICES['1m']}₽")],
            [KeyboardButton(text=f"🏃‍♂️3 месяца - {PLAN_PRICES['3m']}₽")],
            [KeyboardButton(text=f"🧘‍♂️6 месяцев - {PLAN_PRICES['6m']}₽")],
            [KeyboardButton(text="🥑 Главное меню")],
        ],
        resize_keyboard=True,
    )


def payment_methods_kb() -> ReplyKeyboardMarkup:
    """Keyboard with payment method choices."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Банковская карта")],
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

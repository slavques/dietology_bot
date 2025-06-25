from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from .settings import PLAN_PRICES
from .texts import (
    BTN_EDIT,
    BTN_DELETE,
    BTN_SAVE,
    BTN_FULL_PORTION,
    BTN_HALF_PORTION,
    BTN_QUARTER_PORTION,
    BTN_THREEQ_PORTION,
    BTN_BACK,
    BTN_ADD,
    BTN_DAY,
    BTN_WEEK,
    BTN_MONTH,
    BTN_REPORT_DAY,
    BTN_MY_MEALS,
    BTN_SUBSCRIPTION,
    BTN_FAQ,
    BTN_MAIN_MENU,
    BTN_PAY,
    BTN_BACK_TEXT,
    BTN_BANK_CARD,
    BTN_BROADCAST,
)
from typing import Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder


def meal_actions_kb(meal_id: str, clarifications: int = 0) -> InlineKeyboardMarkup:
    """Inline keyboard for meal actions. Hide refine after two clarifications."""
    builder = InlineKeyboardBuilder()
    if clarifications < 2:
        builder.button(text=BTN_EDIT, callback_data=f"edit:{meal_id}")
    builder.button(text=BTN_DELETE, callback_data=f"delete:{meal_id}")
    builder.button(text=BTN_SAVE, callback_data=f"save:{meal_id}")
    if clarifications < 2:
        builder.adjust(3)
    else:
        builder.adjust(2)
    return builder.as_markup()


def save_options_kb(meal_id: str) -> InlineKeyboardMarkup:
    """Keyboard with portion save options."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_FULL_PORTION, callback_data=f"full:{meal_id}")
    builder.button(text=BTN_HALF_PORTION, callback_data=f"half:{meal_id}")
    builder.button(text=BTN_QUARTER_PORTION, callback_data=f"quarter:{meal_id}")
    builder.button(text=BTN_THREEQ_PORTION, callback_data=f"threeq:{meal_id}")
    builder.button(text=BTN_BACK, callback_data=f"back:{meal_id}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_save_kb(meal_id: str) -> InlineKeyboardMarkup:
    """Keyboard asking to confirm addition."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_ADD, callback_data=f"add:{meal_id}")
    builder.button(text=BTN_BACK, callback_data=f"back:{meal_id}")
    builder.adjust(1)
    return builder.as_markup()


def history_nav_kb(offset: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    count = 0
    if offset > 0:
        builder.button(text=BTN_LEFT_HISTORY, callback_data=f"hist:{offset-1}")
        count += 1
    if offset < total - 1:
        builder.button(text=BTN_RIGHT_HISTORY, callback_data=f"hist:{offset+1}")
        count += 1
    if count:
        builder.adjust(count)
    return builder.as_markup()


def stats_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_DAY, callback_data="stats:day")
    builder.button(text=BTN_WEEK, callback_data="stats:week")
    builder.button(text=BTN_MONTH, callback_data="stats:month")
    builder.adjust(3)
    return builder.as_markup()


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Main menu with four actions arranged vertically."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_REPORT_DAY)],
            [KeyboardButton(text=BTN_MY_MEALS)],
            [KeyboardButton(text=BTN_SUBSCRIPTION)],
            [KeyboardButton(text=BTN_FAQ)],
        ],
        resize_keyboard=True,
    )


def back_menu_kb() -> ReplyKeyboardMarkup:
    """Keyboard with a single button to return to the main menu."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_MAIN_MENU)]],
        resize_keyboard=True,
    )


def pay_kb(code: Optional[str] = None) -> InlineKeyboardMarkup:
    """Inline keyboard with a single payment button.

    Optionally encodes the selected plan in callback data so invoice
    handlers can determine which subscription to bill for.
    """
    builder = InlineKeyboardBuilder()
    cb = f"pay:{code}" if code else "pay"
    builder.button(text=BTN_PAY, callback_data=cb)
    builder.adjust(1)
    return builder.as_markup()


def subscription_plans_kb() -> ReplyKeyboardMarkup:
    """Keyboard with subscription duration options."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"🚶‍♂️1 месяц - {PLAN_PRICES['1m']}₽")],
            [KeyboardButton(text=f"🏃‍♂️3 месяца - {PLAN_PRICES['3m']}₽")],
            [KeyboardButton(text=f"🧘‍♂️6 месяцев - {PLAN_PRICES['6m']}₽")],
            [KeyboardButton(text=BTN_MAIN_MENU)],
        ],
        resize_keyboard=True,
    )


def payment_methods_kb() -> ReplyKeyboardMarkup:
    """Keyboard with payment method choices."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BACK_TEXT)],
        ],
        resize_keyboard=True,
    )


def payment_method_inline(code: str) -> InlineKeyboardMarkup:
    """Inline keyboard with a single payment method button."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BANK_CARD, callback_data=f"method:{code}")
    builder.adjust(1)
    return builder.as_markup()


def subscribe_button(text: str) -> InlineKeyboardMarkup:
    """Inline keyboard leading to the subscription menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data="subscribe")
    builder.adjust(1)
    return builder.as_markup()

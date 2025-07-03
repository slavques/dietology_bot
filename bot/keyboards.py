from aiogram.types import (
    InlineKeyboardMarkup,
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
    BTN_STATS,
    BTN_SUBSCRIPTION,
    BTN_FAQ,
    BTN_MAIN_MENU,
    BTN_PAY,
    BTN_BACK_TEXT,
    BTN_BANK_CARD,
    BTN_PLAN_1M,
    BTN_PLAN_3M,
    BTN_PLAN_6M,
    BTN_MANUAL,
    BTN_SETTINGS,
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


def history_nav_kb(offset: int, total: int, include_back: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    count = 0
    if offset > 0:
        builder.button(text=BTN_LEFT_HISTORY, callback_data=f"hist:{offset+1}")
        count += 1
    if offset < total - 1:
        builder.button(text=BTN_RIGHT_HISTORY, callback_data=f"hist:{offset-1}")
        count += 1
    if count:
        builder.adjust(count)
    if include_back:
        builder.button(text=BTN_BACK, callback_data="stats_menu")
        builder.adjust(1)
    return builder.as_markup()


def stats_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_DAY, callback_data="stats:day")
    builder.button(text=BTN_WEEK, callback_data="stats:week")
    builder.button(text=BTN_MONTH, callback_data="stats:month")
    builder.adjust(3)
    return builder.as_markup()


def stats_menu_kb() -> ReplyKeyboardMarkup:
    """Keyboard with stats actions."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_REPORT_DAY)],
            [KeyboardButton(text=BTN_MY_MEALS)],
            [KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Persistent menu with two buttons."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_MAIN_MENU)],
            [KeyboardButton(text=BTN_FAQ)],
        ],
        resize_keyboard=True,
    )


def back_menu_kb() -> ReplyKeyboardMarkup:
    """Same as main_menu_kb for backward compatibility."""
    return main_menu_kb()


def pay_kb(code: Optional[str] = None, include_back: bool = False) -> InlineKeyboardMarkup:
    """Inline keyboard with a payment button and optional back."""
    builder = InlineKeyboardBuilder()
    cb = f"pay:{code}" if code else "pay"
    builder.button(text=BTN_PAY, callback_data=cb)
    if include_back:
        builder.button(text=BTN_BACK, callback_data=f"method_back:{code}")
    builder.adjust(1)
    return builder.as_markup()


def subscription_plans_kb() -> ReplyKeyboardMarkup:
    """Keyboard with subscription duration options."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_PLAN_1M.format(price=PLAN_PRICES['1m']))],
            [KeyboardButton(text=BTN_PLAN_3M.format(price=PLAN_PRICES['3m']))],
            [KeyboardButton(text=BTN_PLAN_6M.format(price=PLAN_PRICES['6m']))],
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


def payment_method_inline(code: str, include_back: bool = False) -> InlineKeyboardMarkup:
    """Inline keyboard with a payment method and optional back button."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BANK_CARD, callback_data=f"method:{code}")
    if include_back:
        builder.button(text=BTN_BACK, callback_data="sub_plans")
    builder.adjust(1)
    return builder.as_markup()


def subscribe_button(text: str) -> InlineKeyboardMarkup:
    """Inline keyboard leading to the subscription menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data="subscribe")
    builder.adjust(1)
    return builder.as_markup()


def menu_inline_kb() -> InlineKeyboardMarkup:
    """Main inline menu under the welcome message."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_MANUAL, callback_data="manual")
    builder.button(text=BTN_STATS, callback_data="stats_menu")
    builder.button(text=BTN_SUBSCRIPTION, callback_data="subscribe")
    builder.button(text=BTN_SETTINGS, callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()


def stats_menu_inline_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_REPORT_DAY, callback_data="report_day")
    builder.button(text=BTN_MY_MEALS, callback_data="my_meals")
    builder.button(text=BTN_BACK, callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def back_inline_kb() -> InlineKeyboardMarkup:
    """Single back button leading to the main menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def subscription_plans_inline_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_PLAN_1M.format(price=PLAN_PRICES['1m']), callback_data="plan:1m")
    builder.button(text=BTN_PLAN_3M.format(price=PLAN_PRICES['3m']), callback_data="plan:3m")
    builder.button(text=BTN_PLAN_6M.format(price=PLAN_PRICES['6m']), callback_data="plan:6m")
    builder.button(text=BTN_BACK, callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()

from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from .settings import PLAN_PRICES, PRO_PLAN_PRICES
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
    BTN_LEFT_HISTORY,
    BTN_RIGHT_HISTORY,
    BTN_PAY,
    BTN_BACK_TEXT,
    BTN_BANK_CARD,
    BTN_TELEGRAM_STARS,
    BTN_CRYPTO,
    BTN_PLAN_1M,
    BTN_PLAN_3M,
    BTN_PLAN_6M,
    BTN_PRO_MODE,
    BTN_LIGHT_MODE,
    BTN_MANUAL,
    BTN_SETTINGS,
    BTN_REMINDERS,
    BTN_GOALS,
    BTN_UPDATE_TIME,
    BTN_MORNING,
    BTN_DAY_REM,
    BTN_EVENING,
    BTN_FEEDBACK,
)
from typing import Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder


def meal_actions_kb(meal_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard for meal actions."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_EDIT, callback_data=f"edit:{meal_id}")
    builder.button(text=BTN_DELETE, callback_data=f"delete:{meal_id}")
    builder.button(text=BTN_SAVE, callback_data=f"save:{meal_id}")
    builder.adjust(3)
    return builder.as_markup()


def refine_back_kb(meal_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard with a back button leading to calculations."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data=f"back:{meal_id}")
    builder.adjust(1)
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


def choose_product_kb(meal_id: str, items: list) -> InlineKeyboardMarkup:
    """Keyboard with product options from FatSecret search."""
    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(items[:3]):
        txt = (
            f"{item['name']} — {item['calories']}/{item['protein']}"
            f"/{item['fat']}/{item['carbs']}"
        )
        builder.button(text=txt, callback_data=f"pick:{meal_id}:{idx}")
    builder.button(text=BTN_EDIT, callback_data=f"lookref:{meal_id}")
    builder.adjust(1)
    return builder.as_markup()


def weight_back_kb(meal_id: str) -> InlineKeyboardMarkup:
    """Keyboard with a single Back button for weight entry."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data=f"lookback:{meal_id}")
    builder.adjust(1)
    return builder.as_markup()


def add_delete_back_kb(meal_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_ADD, callback_data=f"add:{meal_id}")
    builder.button(text=BTN_DELETE, callback_data=f"delete:{meal_id}")
    builder.button(text=BTN_BACK, callback_data=f"lookback:{meal_id}")
    builder.adjust(1)
    return builder.as_markup()


def history_nav_kb(offset: int, include_back: bool = False) -> InlineKeyboardMarkup:
    """Navigation keyboard for history with optional back button."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_LEFT_HISTORY, callback_data=f"hist:{offset+1}")
    if offset > 0:
        builder.button(text=BTN_RIGHT_HISTORY, callback_data=f"hist:{offset-1}")
    if include_back:
        builder.button(text=BTN_BACK, callback_data="stats_menu")
    count = 2 if offset > 0 else 1
    if include_back:
        builder.adjust(count, 1)
    else:
        builder.adjust(count)
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
        is_persistent=True,
    )


def back_menu_kb() -> ReplyKeyboardMarkup:
    """Same as main_menu_kb for backward compatibility."""
    return main_menu_kb()

def pay_kb(code: Optional[str] = None, tier: str = "light", include_back: bool = False) -> InlineKeyboardMarkup:
    """Inline keyboard with a payment button and optional back."""
    builder = InlineKeyboardBuilder()
    cb = f"pay:{tier}:{code}" if code else "pay"
    builder.button(text=BTN_PAY, callback_data=cb)
    if include_back:
        builder.button(text=BTN_BACK_TEXT, callback_data=f"method_back:{tier}:{code}")
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


def payment_method_inline(code: str, tier: str, include_back: bool = False) -> InlineKeyboardMarkup:
    """Inline keyboard with payment methods, filtered by admin settings."""
    from .database import get_option_bool

    builder = InlineKeyboardBuilder()
    if get_option_bool("pay_card"):
        builder.button(text=BTN_BANK_CARD, callback_data=f"method:{tier}:{code}")
    if get_option_bool("pay_stars"):
        builder.button(text=BTN_TELEGRAM_STARS, callback_data=f"method:{tier}:{code}")
    if get_option_bool("pay_crypto"):
        builder.button(text=BTN_CRYPTO, callback_data=f"method:{tier}:{code}")
    if include_back:
        builder.button(text=BTN_BACK_TEXT, callback_data=f"plan_back:{tier}")
    builder.adjust(1)
    return builder.as_markup()


def subscribe_button(text: str) -> InlineKeyboardMarkup:
    """Inline keyboard leading to the subscription menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data="subscribe")
    builder.adjust(1)
    return builder.as_markup()


def feedback_button(url: str) -> InlineKeyboardMarkup:
    """Inline keyboard with a single feedback button."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_FEEDBACK, url=url)
    builder.adjust(1)
    return builder.as_markup()


def subscription_grades_inline_kb() -> InlineKeyboardMarkup:
    """Choose between PRO and light plans based on admin settings."""
    from .database import get_option_bool

    builder = InlineKeyboardBuilder()
    if get_option_bool("grade_pro"):
        builder.button(text=BTN_PRO_MODE, callback_data="grade:pro")
    if get_option_bool("grade_light"):
        builder.button(text=BTN_LIGHT_MODE, callback_data="grade:light")
    builder.button(text=BTN_BACK_TEXT, callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def menu_inline_kb() -> InlineKeyboardMarkup:
    """Main inline menu under the welcome message."""
    from .database import get_option_bool

    builder = InlineKeyboardBuilder()
    if get_option_bool("feat_manual"):
        builder.button(text=BTN_MANUAL, callback_data="manual")
    builder.button(text=BTN_STATS, callback_data="stats_menu")
    builder.button(text=BTN_SUBSCRIPTION, callback_data="subscribe")
    if get_option_bool("feat_settings"):
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


def back_to_reminder_settings_kb() -> InlineKeyboardMarkup:
    """Back button returning to reminder settings."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="reminder_settings")
    builder.adjust(1)
    return builder.as_markup()


def subscription_plans_inline_kb(tier: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prices = PLAN_PRICES if tier == "light" else PRO_PLAN_PRICES
    builder.button(text=BTN_PLAN_1M.format(price=prices['1m']), callback_data=f"plan:{tier}:1m")
    builder.button(text=BTN_PLAN_3M.format(price=prices['3m']), callback_data=f"plan:{tier}:3m")
    builder.button(text=BTN_PLAN_6M.format(price=prices['6m']), callback_data=f"plan:{tier}:6m")
    builder.button(text=BTN_BACK_TEXT, callback_data="sub_grades")
    builder.adjust(1)
    return builder.as_markup()


def settings_menu_kb() -> InlineKeyboardMarkup:
    from .database import get_option_bool

    builder = InlineKeyboardBuilder()
    if get_option_bool("feat_reminders"):
        builder.button(text=BTN_REMINDERS, callback_data="reminders")
    if get_option_bool("feat_goals"):
        builder.button(text=BTN_GOALS, callback_data="goals")
    builder.button(text=BTN_BACK, callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def reminders_main_kb(user) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    on = "🟢"
    off = "🔴"
    builder.button(text=f"{BTN_MORNING} {on if user.morning_enabled else off}", callback_data="toggle_morning")
    builder.button(text=f"{BTN_DAY_REM} {on if user.day_enabled else off}", callback_data="toggle_day")
    builder.button(text=f"{BTN_EVENING} {on if user.evening_enabled else off}", callback_data="toggle_evening")
    builder.button(text=BTN_SETTINGS, callback_data="reminder_settings")
    builder.button(text=BTN_BACK, callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()


def reminders_settings_kb(user) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{BTN_MORNING} - {user.morning_time}", callback_data="set_morning")
    builder.button(text=f"{BTN_DAY_REM} - {user.day_time}", callback_data="set_day")
    builder.button(text=f"{BTN_EVENING} - {user.evening_time}", callback_data="set_evening")
    builder.button(text=BTN_UPDATE_TIME, callback_data="update_tz")
    builder.button(text=BTN_BACK, callback_data="reminders_back")
    builder.adjust(1)
    return builder.as_markup()

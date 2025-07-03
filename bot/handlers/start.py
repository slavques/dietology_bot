from aiogram import types, Dispatcher, F
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..subscriptions import ensure_user, days_left, update_limits
from ..keyboards import main_menu_kb, menu_inline_kb
from ..texts import (
    WELCOME_BASE,
    BTN_MAIN_MENU,
    BTN_BACK,
    REMAINING_FREE,
    REMAINING_DAYS,
    DEV_FEATURE,
)


BASE_TEXT = WELCOME_BASE


def get_welcome_text(user: User) -> str:
    update_limits(user)
    if user.grade == "free":
        remaining = max(user.request_limit - user.requests_used, 0)
        extra = REMAINING_FREE.format(remaining=remaining)
    else:
        days = days_left(user) or 0
        extra = REMAINING_DAYS.format(days=days)
    return f"{BASE_TEXT}\n{extra}"

async def cmd_start(message: types.Message):
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    text = get_welcome_text(user)
    session.commit()
    session.close()
    # Send a temporary message to update the persistent reply keyboard
    tmp = await message.answer("\u2060", reply_markup=main_menu_kb())
    # Main welcome message with inline menu
    await message.answer(text, reply_markup=menu_inline_kb())
    # Remove the helper message so only the welcome text remains
    await tmp.delete()


async def back_to_menu(message: types.Message):
    """Return user to the main menu."""
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    text = get_welcome_text(user)
    session.commit()
    session.close()
    tmp = await message.answer("\u2060", reply_markup=main_menu_kb())
    await message.answer(text, reply_markup=menu_inline_kb())
    await tmp.delete()


async def cb_menu(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    text = get_welcome_text(user)
    session.commit()
    session.close()
    await query.message.edit_text(text)
    await query.message.edit_reply_markup(reply_markup=menu_inline_kb())
    await query.answer()


async def cb_manual(query: types.CallbackQuery):
    await query.message.edit_text(DEV_FEATURE)
    await query.message.edit_reply_markup(reply_markup=menu_inline_kb())
    await query.answer()


async def cb_settings(query: types.CallbackQuery):
    await query.message.edit_text(DEV_FEATURE)
    await query.message.edit_reply_markup(reply_markup=menu_inline_kb())
    await query.answer()


def register(dp: Dispatcher):
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(
        back_to_menu,
        lambda m: m.text in {BTN_MAIN_MENU, BTN_BACK},
    )
    dp.callback_query.register(cb_menu, F.data == "menu")
    dp.callback_query.register(cb_manual, F.data == "manual")
    dp.callback_query.register(cb_settings, F.data == "settings")

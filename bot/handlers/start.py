from aiogram import types, Dispatcher
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..subscriptions import ensure_user, days_left, update_limits
from ..keyboards import main_menu_kb
from ..texts import (
    WELCOME_BASE,
    BTN_MAIN_MENU,
    REMAINING_FREE,
    REMAINING_DAYS,
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
    await message.answer(text, reply_markup=main_menu_kb())


async def back_to_menu(message: types.Message):
    """Return user to the main menu."""
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    text = get_welcome_text(user)
    session.commit()
    session.close()
    await message.answer(text, reply_markup=main_menu_kb())


def register(dp: Dispatcher):
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(
        back_to_menu,
        lambda m: m.text == BTN_MAIN_MENU,
    )

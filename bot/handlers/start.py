from aiogram import types, Dispatcher, F
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..subscriptions import ensure_user, days_left, update_limits, notify_trial_end
from ..keyboards import main_menu_kb, menu_inline_kb
from ..texts import (
    WELCOME_BASE,
    BTN_MAIN_MENU,
    BTN_BACK,
    REMAINING_FREE,
    REMAINING_DAYS,
    TRIAL_STARTED,
)
from ..utils import plural_ru_day


BASE_TEXT = WELCOME_BASE


def get_welcome_text(user: User) -> str:
    update_limits(user)
    if user.grade == "free":
        remaining = max(user.request_limit - user.requests_used, 0)
        extra = REMAINING_FREE.format(remaining=remaining)
        grade_line = ""
    else:
        days = days_left(user) or 0
        extra = REMAINING_DAYS.format(days=days)
        if user.grade.startswith("light"):
            grade_name = "🔸 Старт"
        else:
            grade_name = "⚡ Pro-режим"
        grade_line = f"\nТариф: <b>{grade_name}</b>"
    return f"{BASE_TEXT}{grade_line}\n{extra}"

async def cmd_start(message: types.Message):
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    from ..subscriptions import check_start_trial
    from ..texts import TRIAL_STARTED

    trial = check_start_trial(session, user)
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    text = get_welcome_text(user)
    session.commit()
    session.close()
    # Send a temporary message to update the persistent reply keyboard
    # Send a helper message with the reply keyboard and keep it so the
    # "Меню" and "ЧаВО" buttons remain persistent for the user.
    from ..texts import MENU_STUB

    stub = await message.answer(MENU_STUB, reply_markup=main_menu_kb())
    try:
        await stub.delete()
    except Exception:
        pass
    if trial:
        grade, days = trial
        grade_name = "⚡ Pro-режим" if grade == "pro" else "🔸 Старт"
        await message.answer(
            TRIAL_STARTED.format(
                grade=grade_name, days=days, day_word=plural_ru_day(days)
            ),
            parse_mode="HTML",
        )
    await message.answer(text, reply_markup=menu_inline_kb(), parse_mode="HTML")


async def back_to_menu(message: types.Message):
    """Return user to the main menu."""
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    text = get_welcome_text(user)
    session.commit()
    session.close()
    from ..texts import MENU_STUB

    stub = await message.answer(MENU_STUB, reply_markup=main_menu_kb())
    try:
        await stub.delete()
    except Exception:
        pass
    await message.answer(text, reply_markup=menu_inline_kb(), parse_mode="HTML")


async def cb_menu(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    await notify_trial_end(query.bot, session, user)
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await query.message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        await query.answer()
        return
    text = get_welcome_text(user)
    session.commit()
    session.close()
    await query.message.edit_text(text, parse_mode="HTML")
    await query.message.edit_reply_markup(reply_markup=menu_inline_kb())
    await query.answer()




def register(dp: Dispatcher):
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(
        back_to_menu,
        lambda m: m.text in {BTN_MAIN_MENU, BTN_BACK},
    )
    dp.callback_query.register(cb_menu, F.data == "menu")

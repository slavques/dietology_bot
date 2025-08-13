from aiogram import types, Dispatcher, F
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..subscriptions import ensure_user, days_left, update_limits, notify_trial_end
from ..keyboards import main_menu_kb, menu_inline_kb
from ..texts import (
    WELCOME_BASE,
    WELCOME_INTRO,
    BTN_MAIN_MENU,
    BTN_BACK,
    REMAINING_FREE,
    REMAINING_DAYS,
    TRIAL_STARTED,
    REFERRAL_WELCOME,
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
    args = message.text.split(maxsplit=1)
    payload = args[1] if len(args) > 1 else ""
    referrer_id = None
    if payload.startswith("ref_"):
        try:
            referrer_id = int(payload[4:])
        except ValueError:
            referrer_id = None
    session = SessionLocal()
    existed = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    new_user = existed is None
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    from ..subscriptions import check_start_trial, start_trial
    from ..database import get_option_bool

    trial = None
    referral_msg = None
    if (
        new_user
        and referrer_id
        and referrer_id != message.from_user.id
        and get_option_bool("feat_referral")
    ):
        user.referrer_id = referrer_id
        user.trial_used = True
        start_trial(session, user, 5, "light")
        referral_msg = REFERRAL_WELCOME
    else:
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
    if new_user:
        from ..alerts import new_user as alert_new_user

        await message.answer(WELCOME_INTRO)
        await alert_new_user(message.from_user.id)
    # Send a temporary message to update the persistent reply keyboard
    # Send a helper message with the reply keyboard and keep it so the
    # "Меню" and "ЧаВО" buttons remain persistent for the user.
    from ..texts import MENU_STUB

    stub = await message.answer(MENU_STUB, reply_markup=main_menu_kb())
    if referral_msg:
        await message.answer(referral_msg, parse_mode="HTML")
    elif trial:
        grade, days = trial
        grade_name = "⚡ Pro-режим" if grade == "pro" else "🔸 Старт"
        await message.answer(
            TRIAL_STARTED.format(
                grade=grade_name, days=days, day_word=plural_ru_day(days)
            ),
            parse_mode="HTML",
        )
    await message.answer(text, reply_markup=menu_inline_kb(), parse_mode="HTML")
    try:
        await stub.edit_text("\u2063")
    except Exception:
        pass


async def on_user_left(event: types.ChatMemberUpdated):
    if event.chat.type == "private" and event.new_chat_member.status in {"kicked", "left"}:
        session = SessionLocal()
        user = ensure_user(session, event.from_user.id)
        user.left_bot = True
        session.commit()
        session.close()
        from ..alerts import user_left as alert_user_left

        await alert_user_left(event.from_user.id)


async def on_user_unblocked(event: types.ChatMemberUpdated):
    if (
        event.chat.type == "private"
        and event.new_chat_member.status == "member"
        and event.old_chat_member.status in {"kicked", "left"}
    ):
        session = SessionLocal()
        user = ensure_user(session, event.from_user.id)
        user.left_bot = False
        session.commit()
        session.close()
        from ..alerts import user_unblocked as alert_user_unblocked

        await alert_user_unblocked(event.from_user.id)


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

    try:
        await message.delete()
    except Exception:
        pass
    stub = await message.answer(MENU_STUB, reply_markup=main_menu_kb())
    await message.answer(text, reply_markup=menu_inline_kb(), parse_mode="HTML")
    try:
        await stub.edit_text("\u2063")
    except Exception:
        pass


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
    dp.my_chat_member.register(on_user_left)
    dp.my_chat_member.register(on_user_unblocked)

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import StateFilter
from datetime import timedelta

from ..services import analyze_text
from ..utils import format_meal_message, parse_serving, to_float
from ..keyboards import (
    meal_actions_kb,
    back_menu_kb,
    back_inline_kb,
    subscribe_button,
)
from ..subscriptions import consume_request, ensure_user, notify_trial_end
from ..database import SessionLocal
from ..states import ManualMeal, EditMeal
from ..storage import pending_meals
from ..texts import (
    LIMIT_REACHED_TEXT,
    format_date_ru,
    CLARIFY_PROMPT,
    MANUAL_PROMPT,
    MANUAL_ERROR,
    BTN_EDIT,
    BTN_DELETE,
    BTN_REMOVE_LIMITS,
)
from ..logger import log


async def manual_start(query: types.CallbackQuery, state: FSMContext):
    from ..database import get_option_bool
    from ..texts import FEATURE_DISABLED

    if not get_option_bool("feat_manual"):
        await query.answer(FEATURE_DISABLED, show_alert=True)
        return

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
    session.close()
    await query.message.edit_text(MANUAL_PROMPT, parse_mode="HTML")
    await query.message.edit_reply_markup(reply_markup=back_inline_kb())
    await state.set_state(ManualMeal.waiting_text)
    await query.answer()
    log("notification", "manual input prompt sent to %s", query.from_user.id)


async def process_manual(message: types.Message, state: FSMContext):
    from ..database import get_option_bool
    from ..texts import FEATURE_DISABLED

    if not get_option_bool("feat_manual"):
        await message.answer(FEATURE_DISABLED)
        await state.clear()
        return

    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    ok, reason = consume_request(session, user)
    if not ok:
        if reason == "daily":
            from ..settings import SUPPORT_HANDLE
            from ..texts import PAID_DAILY_LIMIT_TEXT

            await message.answer(
                PAID_DAILY_LIMIT_TEXT.format(support=SUPPORT_HANDLE),
                reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
            )
            log(
                "notification",
                "daily limit message sent to %s",
                message.from_user.id,
            )
        else:
            reset = (
                user.period_end.date()
                if user.period_end
                else (user.period_start + timedelta(days=30)).date()
            )
            text = LIMIT_REACHED_TEXT.format(date=format_date_ru(reset))
            await message.answer(
                text,
                reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
                parse_mode="HTML",
            )
            log(
                "notification",
                "monthly limit message sent to %s",
                message.from_user.id,
            )
        session.close()
        return
    grade = user.grade
    session.close()

    result = await analyze_text(message.text, grade=grade)
    log("prompt", "text analyzed for %s", message.from_user.id)
    if result.get("error") or not result.get("is_food"):
        await message.answer(MANUAL_ERROR)
        log(
            "prompt", "manual text not recognized for %s", message.from_user.id
        )
        return
    name = result.get("name")
    serving = parse_serving(result.get("serving", 0))
    macros = {
        "calories": to_float(result.get("calories", 0)),
        "protein": to_float(result.get("protein", 0)),
        "fat": to_float(result.get("fat", 0)),
        "carbs": to_float(result.get("carbs", 0)),
    }
    meal_id = f"{message.from_user.id}_{message.message_id}"
    pending_meals[meal_id] = {
        "name": name,
        "ingredients": [],
        "type": result.get("type", "meal"),
        "serving": serving,
        "orig_serving": serving,
        "macros": macros,
        "orig_macros": macros.copy(),
        "initial_json": result,
        "text": message.text,
        "chat_id": message.chat.id,
        "message_id": None,
    }
    if not name:
        builder = InlineKeyboardBuilder()
        builder.button(text=BTN_EDIT, callback_data="refine")
        builder.button(text=BTN_DELETE, callback_data="cancel")
        builder.adjust(2)
        await state.update_data(meal_id=meal_id)
        msg = await message.answer(
            CLARIFY_PROMPT,
            reply_markup=builder.as_markup(),
        )
        pending_meals[meal_id]["message_id"] = msg.message_id
        pending_meals[meal_id]["chat_id"] = msg.chat.id
        await state.set_state(EditMeal.waiting_input)
        return
    msg = await message.answer(
        format_meal_message(name, serving, macros),
        reply_markup=meal_actions_kb(meal_id),
    )
    pending_meals[meal_id]["message_id"] = msg.message_id
    pending_meals[meal_id]["chat_id"] = msg.chat.id
    await state.clear()


def register(dp: Dispatcher):
    dp.callback_query.register(manual_start, F.data == "manual")
    dp.message.register(
        process_manual, StateFilter(ManualMeal.waiting_text), F.text
    )

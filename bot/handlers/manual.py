import asyncio
import time
from datetime import timedelta
from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import StateFilter

from ..services import analyze_text, fatsecret_search
from ..utils import format_meal_message, parse_serving, to_float
from ..keyboards import (
    meal_actions_kb,
    back_menu_kb,
    back_inline_kb,
    subscribe_button,
    choose_product_kb,
    weight_back_kb,
    add_delete_back_kb,
)
from ..subscriptions import (
    consume_request,
    ensure_user,
    notify_trial_end,
    has_request_quota,
)
from ..database import SessionLocal
from ..states import ManualMeal, EditMeal, LookupMeal
from ..storage import pending_meals
from ..texts import (
    LIMIT_REACHED_TEXT,
    format_date_ru,
    CLARIFY_PROMPT,
    MANUAL_PROMPT,
    MANUAL_ERROR,
    LOOKUP_PROMPT,
    LOOKUP_WEIGHT,
    BTN_EDIT,
    BTN_DELETE,
    BTN_REMOVE_LIMITS,
)
from ..logger import log
from ..engagement import process_request_events


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
    if not has_request_quota(session, user):
        reset = (
            user.period_end.date()
            if user.period_end
            else (user.period_start + timedelta(days=30)).date()
        )
        text = LIMIT_REACHED_TEXT.format(date=format_date_ru(reset))
        await query.message.edit_text(
            text,
            reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
            parse_mode="HTML",
        )
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

    results = await analyze_text(message.text, grade=grade)
    log("prompt", "text analyzed for %s", message.from_user.id)
    if isinstance(results, list) and results and results[0].get("error"):
        await message.answer(MANUAL_ERROR)
        log("prompt", "manual text not recognized for %s", message.from_user.id)
        asyncio.create_task(process_request_events(message.bot, message.from_user.id))
        return
    if not isinstance(results, list):
        results = [results]
    valid = [r for r in results if r.get("is_food")]
    if not valid:
        await message.answer(MANUAL_ERROR)
        log("prompt", "manual text not recognized for %s", message.from_user.id)
        asyncio.create_task(process_request_events(message.bot, message.from_user.id))
        return

    # suppress reminders for previous pending meals from this user
    for mid, meal in pending_meals.items():
        if mid.startswith(f"{message.from_user.id}_"):
            meal["reminded"] = True

    for idx, res in enumerate(valid, 1):
        meal_id = f"{message.from_user.id}_{message.message_id}_{idx}"
        timestamp = time.time()
        name = res.get("name")
        serving = parse_serving(res.get("serving", 0))
        macros = {
            "calories": to_float(res.get("calories", 0)),
            "protein": to_float(res.get("protein", 0)),
            "fat": to_float(res.get("fat", 0)),
            "carbs": to_float(res.get("carbs", 0)),
        }
        if res.get("google"):
            results = await fatsecret_search(name)
            if results:
                pending_meals[meal_id] = {
                    "initial_json": res,
                    "text": message.text,
                    "chat_id": message.chat.id,
                    "message_id": None,
                    "photo_path": None,
                    "results": results,
                    "ingredients": [],
                    "type": res.get("type", "meal"),
                    "timestamp": timestamp,
                }
                builder = choose_product_kb(meal_id, results)
                await state.update_data(meal_id=meal_id)
                msg = await message.answer(LOOKUP_PROMPT, reply_markup=builder)
                pending_meals[meal_id]["message_id"] = msg.message_id
                pending_meals[meal_id]["chat_id"] = msg.chat.id
                await state.set_state(LookupMeal.choosing)
                continue
        pending_meals[meal_id] = {
            "name": name,
            "ingredients": [],
            "type": res.get("type", "meal"),
            "serving": serving,
            "orig_serving": serving,
            "macros": macros,
            "orig_macros": macros.copy(),
            "initial_json": res,
            "text": message.text,
            "chat_id": message.chat.id,
            "message_id": None,
            "timestamp": timestamp,
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
            continue
        msg = await message.answer(
            format_meal_message(
                name, serving, macros, user_id=message.from_user.id
            ),
            reply_markup=meal_actions_kb(meal_id),
        )
        pending_meals[meal_id]["message_id"] = msg.message_id
        pending_meals[meal_id]["chat_id"] = msg.chat.id
    await state.clear()
    asyncio.create_task(process_request_events(message.bot, message.from_user.id))


def register(dp: Dispatcher):
    dp.callback_query.register(manual_start, F.data == "manual")
    dp.message.register(
        process_manual, StateFilter(ManualMeal.waiting_text), F.text
    )

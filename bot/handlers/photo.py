from datetime import datetime, timedelta
from aiogram import types, Dispatcher, F
import tempfile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..services import analyze_photo, fatsecret_search
from ..utils import format_meal_message, parse_serving, to_float
from ..keyboards import (
    meal_actions_kb,
    back_menu_kb,
    subscribe_button,
    choose_product_kb,
    weight_back_kb,
    add_delete_back_kb,
)
from ..subscriptions import consume_request, ensure_user, has_request_quota, notify_trial_end
from ..database import SessionLocal
from ..states import EditMeal, LookupMeal
from ..storage import pending_meals
from ..texts import (
    LIMIT_REACHED_TEXT,
    format_date_ru,
    REQUEST_PHOTO,
    PHOTO_ANALYZING,
    MULTI_PHOTO_ERROR,
    RECOGNITION_ERROR,
    NO_FOOD_ERROR,
    CLARIFY_PROMPT,
    LOOKUP_PROMPT,
    LOOKUP_WEIGHT,
    BTN_EDIT,
    BTN_DELETE,
    BTN_REMOVE_LIMITS,
)
from ..logger import log


async def request_photo(message: types.Message):
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    if user.grade == "free":
        from ..texts import SUB_REQUIRED, BTN_SUBSCRIPTION
        await message.answer(
            SUB_REQUIRED,
            reply_markup=subscribe_button(BTN_SUBSCRIPTION),
            parse_mode="HTML",
        )
        session.close()
        return
    if not has_request_quota(session, user):
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
            "limit reached message sent to %s",
            message.from_user.id,
        )
        session.close()
        return
    session.close()
    await message.answer(REQUEST_PHOTO, reply_markup=back_menu_kb())
    log(
        "notification", "photo request prompt sent to %s", message.from_user.id
    )


async def handle_photo(message: types.Message, state: FSMContext):
    if message.media_group_id:
        await message.answer(MULTI_PHOTO_ERROR)
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
    if user.grade == "free":
        from ..texts import SUB_REQUIRED, BTN_SUBSCRIPTION
        await message.answer(
            SUB_REQUIRED,
            reply_markup=subscribe_button(BTN_SUBSCRIPTION),
            parse_mode="HTML",
        )
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

    processing_msg = await message.reply(PHOTO_ANALYZING)
    photo = message.photo[-1]
    with tempfile.NamedTemporaryFile(
        prefix="diet_photo_", delete=False
    ) as tmp:
        await message.bot.download(photo.file_id, destination=tmp.name)
        photo_path = tmp.name
    try:
        from PIL import Image

        img = Image.open(photo_path)
        img = img.resize((512, 512), Image.LANCZOS)
        img.save(photo_path, format="JPEG", quality=95)
    except Exception:
        pass
    results = await analyze_photo(photo_path, grade=grade)
    log("prompt", "photo analyzed for %s", message.from_user.id)
    if isinstance(results, list) and results and results[0].get("error"):
        await processing_msg.edit_text(RECOGNITION_ERROR)
        return
    if not isinstance(results, list):
        results = [results]

    valid = [r for r in results if r.get("is_food") and r.get("confidence", 0) >= 0.7]
    if not valid:
        await processing_msg.edit_text(NO_FOOD_ERROR)
        return

    for idx, res in enumerate(valid, 1):
        meal_id = f"{message.from_user.id}_{datetime.utcnow().timestamp()}_{idx}"
        name = res.get("name")
        ingredients = res.get("ingredients", [])
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
                    "photo_path": photo_path,
                    "chat_id": message.chat.id,
                    "message_id": None,
                    "results": results,
                    "ingredients": ingredients,
                    "type": res.get("type", "meal"),
                }
                builder = choose_product_kb(meal_id, results)
                await state.update_data(meal_id=meal_id)
                if idx == 1:
                    await processing_msg.edit_text(LOOKUP_PROMPT, reply_markup=builder)
                    pending_meals[meal_id]["message_id"] = processing_msg.message_id
                    pending_meals[meal_id]["chat_id"] = processing_msg.chat.id
                else:
                    msg = await message.answer(LOOKUP_PROMPT, reply_markup=builder)
                    pending_meals[meal_id]["message_id"] = msg.message_id
                    pending_meals[meal_id]["chat_id"] = msg.chat.id
                await state.set_state(LookupMeal.choosing)
                continue

        pending_meals[meal_id] = {
            "name": name,
            "ingredients": ingredients,
            "type": res.get("type", "meal"),
            "serving": serving,
            "orig_serving": serving,
            "macros": macros,
            "orig_macros": macros.copy(),
            "initial_json": res,
            "photo_path": photo_path,
            "chat_id": message.chat.id,
            "message_id": None,
        }

        if not name:
            builder = InlineKeyboardBuilder()
            builder.button(text=BTN_EDIT, callback_data="refine")
            builder.button(text=BTN_DELETE, callback_data="cancel")
            builder.adjust(2)
            await state.update_data(meal_id=meal_id)
            if idx == 1:
                await processing_msg.edit_text(
                    CLARIFY_PROMPT,
                    reply_markup=builder.as_markup(),
                )
                pending_meals[meal_id]["message_id"] = processing_msg.message_id
                pending_meals[meal_id]["chat_id"] = processing_msg.chat.id
            else:
                msg = await message.answer(
                    CLARIFY_PROMPT,
                    reply_markup=builder.as_markup(),
                )
                pending_meals[meal_id]["message_id"] = msg.message_id
                pending_meals[meal_id]["chat_id"] = msg.chat.id
            await state.set_state(EditMeal.waiting_input)
            continue

        if idx == 1:
            await processing_msg.edit_text(
                format_meal_message(name, serving, macros),
                reply_markup=meal_actions_kb(meal_id),
            )
            pending_meals[meal_id]["message_id"] = processing_msg.message_id
            pending_meals[meal_id]["chat_id"] = processing_msg.chat.id
        else:
            msg = await message.answer(
                format_meal_message(name, serving, macros),
                reply_markup=meal_actions_kb(meal_id),
            )
            pending_meals[meal_id]["message_id"] = msg.message_id
            pending_meals[meal_id]["chat_id"] = msg.chat.id


async def handle_document(message: types.Message):
    await message.answer(MULTI_PHOTO_ERROR)


def register(dp: Dispatcher):
    dp.message.register(handle_photo, F.photo)
    dp.message.register(handle_document, F.document)

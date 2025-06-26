from datetime import datetime, timedelta
from aiogram import types, Dispatcher, F
import tempfile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..services import analyze_photo
from ..utils import format_meal_message, parse_serving, to_float
from ..keyboards import meal_actions_kb, back_menu_kb, subscribe_button
from ..subscriptions import consume_request, ensure_user, has_request_quota
from ..database import SessionLocal
from ..states import EditMeal
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
    BTN_EDIT,
    BTN_DELETE,
    BTN_REMOVE_LIMITS,
)

async def request_photo(message: types.Message):
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    if not has_request_quota(session, user):
        reset = user.period_end.date() if user.period_end else (user.period_start + timedelta(days=30)).date()
        text = LIMIT_REACHED_TEXT.format(date=format_date_ru(reset))
        await message.answer(text, reply_markup=subscribe_button(BTN_REMOVE_LIMITS))
        session.close()
        return
    session.close()
    await message.answer(REQUEST_PHOTO, reply_markup=back_menu_kb())

async def handle_photo(message: types.Message, state: FSMContext):
    if message.media_group_id:
        await message.answer(MULTI_PHOTO_ERROR)
        return
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    if not consume_request(session, user):
        reset = user.period_end.date() if user.period_end else (user.period_start + timedelta(days=30)).date()
        text = LIMIT_REACHED_TEXT.format(date=format_date_ru(reset))
        await message.answer(text, reply_markup=subscribe_button(BTN_REMOVE_LIMITS))
        session.close()
        return
    session.close()

    await message.reply(PHOTO_ANALYZING)
    photo = message.photo[-1]
    with tempfile.NamedTemporaryFile(prefix="diet_photo_", delete=False) as tmp:
        await message.bot.download(photo.file_id, destination=tmp.name)
        photo_path = tmp.name
    result = await analyze_photo(photo_path)
    if result.get('error'):
        await message.answer(RECOGNITION_ERROR)
        return
    if not result.get('is_food') or result.get('confidence', 0) < 0.7:
        await message.answer(NO_FOOD_ERROR)
        return

    name = result.get('name')
    ingredients = result.get('ingredients', [])
    serving = parse_serving(result.get('serving', 0))
    macros = {
        'calories': to_float(result.get('calories', 0)),
        'protein': to_float(result.get('protein', 0)),
        'fat': to_float(result.get('fat', 0)),
        'carbs': to_float(result.get('carbs', 0)),
    }

    meal_id = f"{message.from_user.id}_{datetime.utcnow().timestamp()}"
    pending_meals[meal_id] = {
        'name': name,
        'ingredients': ingredients,
        'type': result.get('type', 'meal'),
        'serving': serving,
        'orig_serving': serving,
        'macros': macros,
        'orig_macros': macros.copy(),
        'photo_path': photo_path,
        'clarifications': 0,
        'chat_id': message.chat.id,
        'message_id': None,
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
        reply_markup=meal_actions_kb(meal_id, clarifications=0)
    )
    pending_meals[meal_id]["message_id"] = msg.message_id
    pending_meals[meal_id]["chat_id"] = msg.chat.id


async def handle_document(message: types.Message):
    await message.answer(MULTI_PHOTO_ERROR)


def register(dp: Dispatcher):
    dp.message.register(handle_photo, F.photo)
    dp.message.register(handle_document, F.document)

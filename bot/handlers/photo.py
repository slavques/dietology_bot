from datetime import datetime
from aiogram import types, Dispatcher, F
import tempfile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..services import analyze_photo, analyze_photo_with_hint
from ..utils import format_meal_message, parse_serving, to_float
from ..keyboards import meal_actions_kb, back_menu_kb
from ..states import EditMeal
from ..storage import pending_meals

async def request_photo(message: types.Message):
    await message.answer(
        "\U0001F525\u041E\u0442\u043B\u0438\u0447\u043D\u043E! \u041E\u0442\u043F\u0440\u0430\u0432\u044C \u0444\u043E\u0442\u043E \u0435\u0434\u044B \u2014 \u044F \u0432\u0441\u0451 \u043F\u043E\u0441\u0447\u0438\u0442\u0430\u044E \u0441\u0430\u043C.",
        reply_markup=back_menu_kb(),
    )

async def handle_photo(message: types.Message, state: FSMContext):
    if message.media_group_id:
        await message.answer(
            "🤖 Хм… похоже, ты отправил сразу несколько изображений или файл в неподдерживаемом формате.\n\n"
            "Пришли, пожалуйста, одно фото блюда — и я всё рассчитаю!"
        )
        return

    await message.reply("Готово! 🔍\nАнализирую фото…")
    photo = message.photo[-1]
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        await message.bot.download(photo.file_id, destination=tmp.name)
        photo_path = tmp.name
    result = await analyze_photo(photo_path)
    if result.get('error'):
        await message.answer("Сервис распознавания недоступен. Попробуйте позднее.")
        return
    if not result.get('is_food') or result.get('confidence', 0) < 0.7:
        await message.answer(
            "🤔 Еду на этом фото найти не удалось.\n"
            "Попробуй отправить другое изображение — постараюсь распознать."
        )
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
        'serving': serving,
        'macros': macros,
        'photo_path': photo_path,
        'clarifications': 0,
        'chat_id': message.chat.id,
        'message_id': None,
    }

    if not name:
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Уточнить", callback_data="refine")
        builder.button(text="🗑 Удалить", callback_data="cancel")
        builder.adjust(2)
        await state.update_data(meal_id=meal_id)
        msg = await message.answer(
            "🤔 Не удалось точно распознать блюдо на фото.\n"
            "Можешь ввести название и вес вручную?",
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
    await message.answer(
        "🤖 Хм… похоже, ты отправил сразу несколько изображений или файл в неподдерживаемом формате.\n\n"
        "Пришли, пожалуйста, одно фото блюда — и я всё рассчитаю!"
    )


def register(dp: Dispatcher):
    dp.message.register(request_photo, F.text == "📸 Новое фото")
    dp.message.register(handle_photo, F.photo)
    dp.message.register(handle_document, F.document)

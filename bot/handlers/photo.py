from datetime import datetime
from aiogram import types, Dispatcher, F
import tempfile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..services import classify_food, recognize_dish, calculate_macros
from ..utils import format_meal_message
from ..keyboards import meal_actions_kb, back_menu_kb
from ..states import EditMeal
from ..storage import pending_meals

async def request_photo(message: types.Message):
    await message.answer(
        "\U0001F525\u041E\u0442\u043B\u0438\u0447\u043D\u043E! \u041E\u0442\u043F\u0440\u0430\u0432\u044C \u0444\u043E\u0442\u043E \u0435\u0434\u044B \u2014 \u044F \u0432\u0441\u0451 \u043F\u043E\u0441\u0447\u0438\u0442\u0430\u044E \u0441\u0430\u043C.",
        reply_markup=back_menu_kb(),
    )

async def handle_photo(message: types.Message, state: FSMContext):
    await message.reply("Готово! \ud83d\udd0d\nАнализирую фото…")
    photo = message.photo[-1]
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        await message.bot.download(photo.file_id, destination=tmp.name)
        photo_path = tmp.name
    classification = await classify_food(photo_path)
    if classification.get('error'):
        await message.answer("Сервис распознавания недоступен. Попробуйте позднее.")
        return
    if not classification['is_food'] or classification['confidence'] < 0.7:
        await message.answer(
            "\ud83e\udd14 \u0415\u0434\u0443 \u043d\u0430 \u044d\u0442\u043e\u043c \u0444\u043e\u0442\u043e \u043d\u0430\u0439\u0442\u0438 \u043d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c.\n"
            "\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0434\u0440\u0443\u0433\u043e\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u2014 \u043f\u043e\u0441\u0442\u0430\u0440\u0430\u044e\u0441\u044c \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0442\u044c."
        )
        return

    dish = await recognize_dish(photo_path)
    if dish.get('error'):
        await message.answer("Сервис распознавания недоступен. Попробуйте позднее.")
        return
    name = dish.get('name')
    ingredients = dish.get('ingredients', [])
    serving = dish.get('serving', 0)

    if not name:
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Уточнить", callback_data="refine")
        builder.button(text="🗑 Удалить", callback_data="cancel")
        builder.adjust(2)
        await state.update_data(photo_path=photo_path, ingredients=ingredients, serving=serving)
        await message.answer(
            "\ud83e\udd14 \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0442\u043e\u0447\u043d\u043e \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0442\u044c \u0431\u043b\u044e\u0434\u043e \u043d\u0430 \u0444\u043e\u0442\u043e.\n\u041c\u043e\u0436\u0435\u0448\u044c \u0432\u0432\u0435\u0441\u0442\u0438 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0438 \u0432\u0435\u0441 \u0432\u0440\u0443\u0447\u043d\u0443\u044e?",
            reply_markup=builder.as_markup(),
        )
        await state.set_state(EditMeal.waiting_input)
        return

    macros = await calculate_macros(ingredients, serving)
    if macros.get('error'):
        await message.answer("Сервис расчета недоступен. Попробуйте позднее.")
        return
    meal_id = f"{message.from_user.id}_{datetime.utcnow().timestamp()}"
    pending_meals[meal_id] = {
        'name': name,
        'ingredients': ingredients,
        'serving': serving,
        'macros': macros,
    }

    await message.answer(
        format_meal_message(name, serving, macros),
        reply_markup=meal_actions_kb(meal_id)
    )


def register(dp: Dispatcher):
    dp.message.register(request_photo, F.text == "\U0001F4F8 Новое фото")
    dp.message.register(handle_photo, F.photo)

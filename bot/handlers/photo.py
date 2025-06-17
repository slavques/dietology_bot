from datetime import datetime
from aiogram import types, Dispatcher, F
import tempfile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..services import classify_food, recognize_dish, calculate_macros
from ..utils import format_meal_message
from ..keyboards import meal_actions_kb
from ..states import EditMeal
from ..storage import pending_meals


async def request_photo(message: types.Message):
    await message.answer("Отправьте фото блюда.")

async def handle_photo(message: types.Message, state: FSMContext):
    await message.reply("Получил, анализирую…")
    photo = message.photo[-1]
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        await message.bot.download(photo.file_id, destination=tmp.name)
        photo_path = tmp.name
    classification = await classify_food(photo_path)

    if classification.get('error'):
        await message.answer("Сервис распознавания недоступен. Попробуйте позднее.")
        return
    if not classification['is_food'] or classification['confidence'] < 0.7:
        await message.answer("Я не увидел еду на фото, попробуйте снова.")
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
        builder.button(text="Уточнить вес/ингр.", callback_data="refine")
        await state.update_data(photo_path=photo_path, ingredients=ingredients, serving=serving)
        await message.answer(
            "Не смог распознать блюдо. Уточните вес/ингредиенты.",
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

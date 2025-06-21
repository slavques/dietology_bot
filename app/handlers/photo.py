from datetime import datetime
from typing import List

from aiogram import types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State

from ..data import pending_meals
from ..services import classify_food, recognize_dish, calculate_macros
from ..keyboards import meal_actions_keyboard
from ..utils import format_meal_message


class EditMeal(StatesGroup):
    waiting_input = State()


def setup(dp: Dispatcher):
    @dp.message_handler(content_types=types.ContentType.PHOTO)
    async def handle_photo(message: types.Message, state: FSMContext):
        await message.reply("Получил, анализирую…")
        photo = message.photo[-1]
        photo_file = await photo.download()
        classification = await classify_food(photo_file.name)
        if not classification["is_food"] or classification["confidence"] < 0.7:
            await message.answer("Я не увидел еду на фото, попробуйте снова.")
            return

        dish = await recognize_dish(photo_file.name)
        name = dish.get("name")
        ingredients: List[str] = dish.get("ingredients", [])
        serving = dish.get("serving", 0)

        if not name:
            markup = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Уточнить вес/ингр.", callback_data="refine")
            )
            await state.update_data(photo_path=photo_file.name, ingredients=ingredients, serving=serving)
            await message.answer("Не смог распознать блюдо. Уточните вес/ингредиенты.", reply_markup=markup)
            await EditMeal.waiting_input.set()
            return

        macros = await calculate_macros(ingredients, serving)
        meal_id = f"{message.from_user.id}_{datetime.utcnow().timestamp()}"
        pending_meals[meal_id] = {
            "name": name,
            "ingredients": ingredients,
            "serving": serving,
            "macros": macros,
        }
        await message.answer(format_meal_message(name, serving, macros), reply_markup=meal_actions_keyboard(meal_id))

    @dp.message_handler(state=EditMeal.waiting_input)
    async def process_edit(message: types.Message, state: FSMContext):
        data = await state.get_data()
        meal_id = data.get("meal_id", f"{message.from_user.id}_{datetime.utcnow().timestamp()}")
        parts = message.text.split()
        if len(parts) >= 2 and parts[-1].replace('.', '', 1).isdigit():
            serving = float(parts[-1])
            name = " ".join(parts[:-1])
        else:
            name = message.text
            serving = 100.0
        ingredients = [name]
        macros = await calculate_macros(ingredients, serving)
        pending_meals[meal_id] = {
            "name": name,
            "ingredients": ingredients,
            "serving": serving,
            "macros": macros,
        }
        await message.answer(format_meal_message(name, serving, macros), reply_markup=meal_actions_keyboard(meal_id))
        await state.finish()

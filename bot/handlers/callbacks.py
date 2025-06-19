from datetime import datetime
from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from ..database import SessionLocal, User, Meal
from ..services import analyze_photo_with_hint
from ..utils import format_meal_message
from ..keyboards import meal_actions_kb, save_options_kb
from ..states import EditMeal
from ..storage import pending_meals


async def cb_refine(query: types.CallbackQuery, state: FSMContext):
    """Prompt user to enter name and weight manually."""
    await query.bot.send_message(
        query.from_user.id,
        "✏️ Хорошо!\n"
        "Напиши название блюда и его вес (в граммах).\n\n"
        "Например: Паста с соусом, 250 г",
    )
    await state.set_state(EditMeal.waiting_input)
    await query.answer()


async def cb_cancel(query: types.CallbackQuery, state: FSMContext):
    """Cancel current operation."""
    data = await state.get_data()
    meal_id = data.get('meal_id')
    if meal_id:
        pending_meals.pop(meal_id, None)
    await state.clear()
    await query.message.delete()
    await query.answer()
    await query.bot.send_message(
        query.from_user.id,
        "🗑 Запись удалена.\nЕсли хочешь отправить другое блюдо — просто пришли фото",
    )

async def cb_edit(query: types.CallbackQuery, state: FSMContext):
    meal_id = query.data.split(':', 1)[1]
    await state.update_data(meal_id=meal_id)
    await query.bot.send_message(
        query.from_user.id,
        "✏️ Хорошо!\n"
        "Напиши название блюда и его вес (в граммах).\n\n"
        "Например: Паста с соусом, 250 г",
    )
    await state.set_state(EditMeal.waiting_input)
    await query.answer()

async def process_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    meal_id = data.get('meal_id')
    if not meal_id or meal_id not in pending_meals:
        await message.answer("Сессия устарела. Отправьте фото заново.")
        await state.clear()
        return
    meal = pending_meals[meal_id]

    result = await analyze_photo_with_hint(meal['photo_path'], message.text)
    if result.get('error') or not result.get('name'):
        await message.answer(
            "Не удалось обработать уточнение. "
            "Напишите, пожалуйста, название блюда и при необходимости вес или ингредиенты.\n"
            "Примеры: \"Паста с соусом, 250 г\" или \"Помидор 100 г, огурец 50 г\""
        )
        return
    meal.update({
        'name': result['name'],
        'ingredients': result.get('ingredients', []),
        'serving': result.get('serving', 0),
        'macros': {
            'calories': result.get('calories', 0),
            'protein': result.get('protein', 0),
            'fat': result.get('fat', 0),
            'carbs': result.get('carbs', 0),
        },
    })
    meal['clarifications'] += 1
    await message.answer(
        format_meal_message(meal['name'], meal['serving'], meal['macros']),
        reply_markup=meal_actions_kb(meal_id, meal['clarifications'])
    )
    await state.clear()

async def cb_delete(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    pending_meals.pop(meal_id, None)
    await query.message.delete()
    await query.answer()
    await query.bot.send_message(
        query.from_user.id,
        "🗑 Запись удалена.\nЕсли хочешь отправить другое блюдо — просто пришли фото",
    )

async def cb_save(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    if meal_id not in pending_meals:
        await query.answer("Сессия устарела", show_alert=True)
        return
    await query.message.edit_reply_markup(reply_markup=save_options_kb(meal_id))
    await query.answer()


async def _final_save(query: types.CallbackQuery, meal_id: str, half: bool = False):
    meal = pending_meals.pop(meal_id, None)
    if not meal:
        await query.answer("Нечего сохранять", show_alert=True)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        user = User(telegram_id=query.from_user.id)
        session.add(user)
        session.commit()
    serving = meal['serving'] / 2 if half else meal['serving']
    macros = meal['macros']
    if half:
        macros = {k: v / 2 for k, v in macros.items()}
    name = meal['name']
    if half:
        name = "1/2 " + name
    new_meal = Meal(
        user_id=user.id,
        name=name,
        ingredients=','.join(meal['ingredients']),
        serving=serving,
        calories=macros['calories'],
        protein=macros['protein'],
        fat=macros['fat'],
        carbs=macros['carbs'],
    )
    session.add(new_meal)
    session.commit()
    session.close()
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer()
    await query.bot.send_message(
        query.from_user.id,
        "✅ Готово! Блюдо добавлено в историю.\n"
        "📂 Хочешь посмотреть приёмы за сегодня — нажми ниже \n\"🧾 Отчёт за день\"",
    )


async def cb_save_full(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    await _final_save(query, meal_id, half=False)


async def cb_save_half(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    await _final_save(query, meal_id, half=True)


async def cb_save_back(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.get(meal_id)
    if meal:
        await query.message.edit_reply_markup(
            reply_markup=meal_actions_kb(meal_id, meal.get('clarifications', 0))
        )
    await query.answer()

def register(dp: Dispatcher):
    dp.callback_query.register(cb_edit, F.data.startswith('edit:'))
    dp.callback_query.register(cb_refine, F.data == 'refine')
    dp.callback_query.register(cb_cancel, F.data == 'cancel')
    dp.message.register(process_edit, StateFilter(EditMeal.waiting_input))
    dp.callback_query.register(cb_delete, F.data.startswith('delete:'))
    dp.callback_query.register(cb_save, F.data.startswith('save:'))
    dp.callback_query.register(cb_save_full, F.data.startswith('full:'))
    dp.callback_query.register(cb_save_half, F.data.startswith('half:'))
    dp.callback_query.register(cb_save_back, F.data.startswith('back:'))

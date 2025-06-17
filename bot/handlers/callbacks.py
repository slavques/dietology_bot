from datetime import datetime
from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from ..database import SessionLocal, User, Meal
from ..services import calculate_macros
from ..utils import format_meal_message
from ..keyboards import meal_actions_kb
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
    meal_id = data.get('meal_id', f"{message.from_user.id}_{datetime.utcnow().timestamp()}")
    parts = message.text.split()
    if len(parts) >= 2 and parts[-1].replace('.', '', 1).isdigit():
        serving = float(parts[-1])
        name = ' '.join(parts[:-1])
    else:
        name = message.text
        serving = 100.0
    ingredients = [name]
    macros = await calculate_macros(ingredients, serving)
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
    new_meal = Meal(
        user_id=user.id,
        name=meal['name'],
        ingredients=','.join(meal['ingredients']),
        serving=meal['serving'],
        calories=meal['macros']['calories'],
        protein=meal['macros']['protein'],
        fat=meal['macros']['fat'],
        carbs=meal['macros']['carbs'],
    )
    session.add(new_meal)
    session.commit()
    session.close()
    await query.answer()
    await query.bot.send_message(
        query.from_user.id,
        "✅ Готово! Блюдо добавлено в историю.\n"
        "📂 Хочешь посмотреть приёмы за сегодня — нажми ниже \n\"🧾 Отчёт за день\"",
    )


def register(dp: Dispatcher):
    dp.callback_query.register(cb_edit, F.data.startswith('edit:'))
    dp.callback_query.register(cb_refine, F.data == 'refine')
    dp.callback_query.register(cb_cancel, F.data == 'cancel')
    dp.message.register(process_edit, StateFilter(EditMeal.waiting_input))
    dp.callback_query.register(cb_delete, F.data.startswith('delete:'))
    dp.callback_query.register(cb_save, F.data.startswith('save:'))

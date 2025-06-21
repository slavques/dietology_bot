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
    """Prompt user to enter name and weight manually within the same message."""
    await query.message.edit_text(
        "✏️ Хорошо!\n"
        "Напиши название блюда и его вес (в граммах).\n\n"
        "Например: Паста с соусом, 250 г",
        reply_markup=None,
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
    await query.message.edit_text(
        "✏️ Хорошо!\n"
        "Напиши название блюда и его вес (в граммах).\n\n"
        "Например: Паста с соусом, 250 г",
        reply_markup=None,
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
    MAX_LEN = 200
    if not message.text or len(message.text) > MAX_LEN:
        await message.answer(
            f"Уточнение должно быть текстом до {MAX_LEN} символов."
        )
        return

    result = await analyze_photo_with_hint(meal['photo_path'], message.text)
    if result.get('error') or not result.get('success'):
        await message.answer(
            "Не удалось обработать уточнение. Попробуй ещё раз."
        )
        return
    meal.update({
        'name': result.get('name', meal['name']),
        'serving': result.get('serving', meal['serving']),
        'macros': {
            'calories': result.get('calories', meal['macros']['calories']),
            'protein': result.get('protein', meal['macros']['protein']),
            'fat': result.get('fat', meal['macros']['fat']),
            'carbs': result.get('carbs', meal['macros']['carbs']),
        },
    })
    meal['clarifications'] += 1
    await message.delete()
    await message.bot.edit_message_text(
        text=format_meal_message(meal['name'], meal['serving'], meal['macros']),
        chat_id=meal['chat_id'],
        message_id=meal['message_id'],
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


async def _final_save(query: types.CallbackQuery, meal_id: str, fraction: float = 1.0):
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
    serving = meal['serving'] * fraction
    macros = {k: v * fraction for k, v in meal['macros'].items()}
    prefixes = {1.0: "", 0.5: "1/2 ", 0.25: "1/4 ", 0.75: "3/4 "}
    name = prefixes.get(fraction, "") + meal['name']
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
    await _final_save(query, meal_id, fraction=1.0)


async def cb_save_half(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    await _final_save(query, meal_id, fraction=0.5)


async def cb_save_quarter(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    await _final_save(query, meal_id, fraction=0.25)


async def cb_save_threeq(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    await _final_save(query, meal_id, fraction=0.75)


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
    dp.message.register(process_edit, StateFilter(EditMeal.waiting_input), F.text)
    dp.callback_query.register(cb_delete, F.data.startswith('delete:'))
    dp.callback_query.register(cb_save, F.data.startswith('save:'))
    dp.callback_query.register(cb_save_full, F.data.startswith('full:'))
    dp.callback_query.register(cb_save_half, F.data.startswith('half:'))
    dp.callback_query.register(cb_save_quarter, F.data.startswith('quarter:'))
    dp.callback_query.register(cb_save_threeq, F.data.startswith('threeq:'))
    dp.callback_query.register(cb_save_back, F.data.startswith('back:'))

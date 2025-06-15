from datetime import datetime

from aiogram import types
from aiogram.dispatcher import Dispatcher, FSMContext

from ..data import pending_meals
from ..db import SessionLocal
from ..models import User, Meal
from ..keyboards import meal_actions_keyboard
from ..utils import format_meal_message
from .photo import EditMeal
from ..services import calculate_macros


def setup(dp: Dispatcher):
    @dp.callback_query_handler(lambda c: c.data.startswith("edit:"))
    async def cb_edit(query: types.CallbackQuery, state: FSMContext):
        meal_id = query.data.split(":", 1)[1]
        await state.update_data(meal_id=meal_id)
        await query.message.answer("Введите название и вес, напр. 'Яблоко 150'")
        await EditMeal.waiting_input.set()
        await query.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("delete:"))
    async def cb_delete(query: types.CallbackQuery):
        meal_id = query.data.split(":", 1)[1]
        pending_meals.pop(meal_id, None)
        await query.message.delete()
        await query.answer("Удалено")

    @dp.callback_query_handler(lambda c: c.data.startswith("save:"))
    async def cb_save(query: types.CallbackQuery):
        meal_id = query.data.split(":", 1)[1]
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
            name=meal["name"],
            ingredients=",".join(meal["ingredients"]),
            serving=meal["serving"],
            calories=meal["macros"]["calories"],
            protein=meal["macros"]["protein"],
            fat=meal["macros"]["fat"],
            carbs=meal["macros"]["carbs"],
        )
        session.add(new_meal)
        session.commit()
        session.close()
        await query.answer("Сохранено в историю!")

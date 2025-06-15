from datetime import datetime, timedelta
from aiogram import types, Dispatcher, F
from aiogram.filters import Command
from ..database import SessionLocal, Meal, User
from ..utils import make_bar_chart
from ..keyboards import stats_period_kb

async def cmd_stats(message: types.Message):
    await message.answer("Выберите период:", reply_markup=stats_period_kb())

async def cb_stats(query: types.CallbackQuery):
    period = query.data.split(':', 1)[1]
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        await query.answer("Нет данных", show_alert=True)
        session.close()
        return
    now = datetime.utcnow()
    if period == 'day':
        start = now - timedelta(days=1)
    elif period == 'week':
        start = now - timedelta(weeks=1)
    else:
        start = now - timedelta(days=30)
    meals = session.query(Meal).filter(Meal.user_id == user.id, Meal.timestamp >= start).all()
    session.close()
    if not meals:
        await query.message.edit_text("Нет данных за выбранный период.")
        await query.answer()
        return
    totals = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carbs': 0.0}
    for m in meals:
        totals['calories'] += m.calories
        totals['protein'] += m.protein
        totals['fat'] += m.fat
        totals['carbs'] += m.carbs
    text = (
        f"Всего за период:\n"
        f"{totals['calories']} ккал / {totals['protein']} г / {totals['fat']} г / {totals['carbs']} г\n\n"
        f"{make_bar_chart(totals)}"
    )
    await query.message.edit_text(text)
    await query.answer()


def register(dp: Dispatcher):
    dp.message.register(cmd_stats, Command('stats'))
    dp.callback_query.register(cb_stats, F.data.startswith('stats:'))
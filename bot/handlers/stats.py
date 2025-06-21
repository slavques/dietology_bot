from datetime import datetime, timedelta
from aiogram import types, Dispatcher, F
from aiogram.filters import Command

from ..database import SessionLocal, Meal, User
from ..utils import make_bar_chart
from ..keyboards import stats_period_kb, back_menu_kb

async def cmd_stats(message: types.Message):
    await message.answer(
        "Выберите период:", reply_markup=stats_period_kb()
    )

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


async def report_day(message: types.Message):
    """Send today's meal report with totals and list."""
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        await message.answer("Нет данных", reply_markup=back_menu_kb())
        session.close()
        return
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    meals = (
        session.query(Meal)
        .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
        .order_by(Meal.timestamp)
        .all()
    )
    session.close()
    if not meals:
        await message.answer(
            "\ud83d\udcdd \u041e\u0442\u0447\u0451\u0442 \u0437\u0430 \u0434\u0435\u043d\u044c\n\n"
            "\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u043d\u0438 \u043e\u0434\u043d\u043e\u0433\u043e \u043f\u0440\u0438\u0451\u043c\u0430 \u043f\u0438\u0449\u0438.\n\n"
            "\ud83d\udcf8 \u041e\u0442\u043f\u0440\u0430\u0432\u044c \u0444\u043e\u0442\u043e \u0435\u0434\u044b \u2014 \u0438 \u044f \u0434\u043e\u0431\u0430\u0432\u043b\u044e \u043f\u0435\u0440\u0432\u0443\u044e \u0437\u0430\u043f\u0438\u0441\u044c!",
            reply_markup=back_menu_kb(),
        )
        return

    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for m in meals:
        totals["calories"] += m.calories
        totals["protein"] += m.protein
        totals["fat"] += m.fat
        totals["carbs"] += m.carbs

    lines = [
        "\ud83d\udcdd \u041e\u0442\u0447\u0451\u0442 \u0437\u0430 \u0434\u0435\u043d\u044c",
        "",
        "\ud83d\udcca \u0418\u0442\u043e\u0433\u043e:",
        f"\u2022 \ud83d\udd25 \u041a\u0430\u043b\u043e\u0440\u0438\u0438: {int(totals['calories'])} \u043a\u043a\u0430\u043b",
        f"\u2022 \u0411\u0435\u043b\u043a\u0438: {int(totals['protein'])} \u0433  ",
        f"\u2022 \u0416\u0438\u0440\u044b: {int(totals['fat'])} \u0433  ",
        f"\u2022 \u0423\u0433\u043b\u0435\u0432\u043E\u0434\u044B: {int(totals['carbs'])} \u0433  ",
        "",
        "\ud83d\udcc2 \u041f\u0440\u0438\u0451\u043c\u044b \u043f\u0438\u0449\u0438:",
    ]
    for meal in meals:
        lines.append(
            f"\u2022 {meal.name}\n(\u0411\u0435\u043b\u043a\u0438: {int(meal.protein)} \u0433 / \u0416\u0438\u0440\u044b: {int(meal.fat)} \u0433  / \u0423\u0433\u043B\u0435\u0432\u043E\u0434\u044B: {int(meal.carbs)} \u0433)"
        )
    await message.answer("\n".join(lines), reply_markup=back_menu_kb())


def register(dp: Dispatcher):
    dp.message.register(cmd_stats, Command('stats'))
    dp.message.register(report_day, F.text == "\U0001F9FE \u041E\u0442\u0447\u0451\u0442 \u0437\u0430 \u0434\u0435\u043D\u044C")
    dp.callback_query.register(cb_stats, F.data.startswith('stats:'))

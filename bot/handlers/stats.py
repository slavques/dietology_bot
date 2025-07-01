from datetime import datetime, timedelta
from aiogram import types, Dispatcher, F
from aiogram.filters import Command

from ..database import SessionLocal, Meal, User
from ..utils import make_bar_chart
from ..keyboards import stats_period_kb, main_menu_kb, stats_menu_kb
from ..texts import (
    STATS_CHOOSE_PERIOD,
    STATS_NO_DATA,
    STATS_NO_DATA_PERIOD,
    STATS_TOTALS,
    REPORT_EMPTY,
    REPORT_HEADER,
    REPORT_TOTAL,
    REPORT_LINE_CAL,
    REPORT_LINE_P,
    REPORT_LINE_F,
    REPORT_LINE_C,
    REPORT_MEALS_TITLE,
    MEAL_LINE,
    BTN_REPORT_DAY,
    BTN_STATS,
    STATS_MENU_TEXT,
    BTN_BACK,
)

async def show_stats_menu(message: types.Message):
    await message.answer(STATS_MENU_TEXT, reply_markup=stats_menu_kb())

async def cmd_stats(message: types.Message):
    await message.answer(
        STATS_CHOOSE_PERIOD, reply_markup=stats_period_kb()
    )

async def cb_stats(query: types.CallbackQuery):
    period = query.data.split(':', 1)[1]
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        await query.answer(STATS_NO_DATA, show_alert=True)
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
        await query.message.edit_text(STATS_NO_DATA_PERIOD)
        await query.answer()
        return
    totals = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carbs': 0.0}
    for m in meals:
        totals['calories'] += m.calories
        totals['protein'] += m.protein
        totals['fat'] += m.fat
        totals['carbs'] += m.carbs
    text = STATS_TOTALS.format(
        calories=int(totals['calories']),
        protein=int(totals['protein']),
        fat=int(totals['fat']),
        carbs=int(totals['carbs']),
        chart=make_bar_chart(totals),
    )
    await query.message.edit_text(text)
    await query.answer()


async def report_day(message: types.Message):
    """Send today's meal report with totals and list."""
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        await message.answer(STATS_NO_DATA, reply_markup=main_menu_kb())
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
            REPORT_EMPTY,
            reply_markup=main_menu_kb(),
        )
        return

    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for m in meals:
        totals["calories"] += m.calories
        totals["protein"] += m.protein
        totals["fat"] += m.fat
        totals["carbs"] += m.carbs

    lines = [
        REPORT_HEADER,
        "",
        REPORT_TOTAL,
        REPORT_LINE_CAL.format(cal=int(totals['calories'])),
        REPORT_LINE_P.format(protein=int(totals['protein'])),
        REPORT_LINE_F.format(fat=int(totals['fat'])),
        REPORT_LINE_C.format(carbs=int(totals['carbs'])),
        "",
        REPORT_MEALS_TITLE,
    ]

    dishes = []
    drinks = []
    for meal in meals:
        icon = '🥤' if getattr(meal, 'type', 'meal') == 'drink' else '🍜'
        line = MEAL_LINE.format(
            icon=icon,
            name=meal.name,
            protein=int(meal.protein),
            fat=int(meal.fat),
            carbs=int(meal.carbs),
        )
        if getattr(meal, 'type', 'meal') == 'drink':
            drinks.append(line)
        else:
            dishes.append(line)

    lines.extend(dishes)
    if drinks:
        lines.append("")
        lines.extend(drinks)

    await message.answer("\n".join(lines), reply_markup=main_menu_kb())


def register(dp: Dispatcher):
    dp.message.register(cmd_stats, Command('stats'))
    dp.message.register(show_stats_menu, F.text == BTN_STATS)
    dp.message.register(report_day, F.text == BTN_REPORT_DAY)
    dp.callback_query.register(cb_stats, F.data.startswith('stats:'))

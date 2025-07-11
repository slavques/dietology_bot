from datetime import datetime, timedelta
from aiogram import types, Dispatcher, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..database import SessionLocal, Meal, User
from ..utils import make_bar_chart
from ..keyboards import (
    stats_period_kb,
    main_menu_kb,
    stats_menu_kb,  # kept for legacy
    stats_menu_inline_kb,
    menu_inline_kb,
    history_nav_kb,
)
from .history import build_history_text
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
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if user and user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    session.close()
    await message.answer(STATS_MENU_TEXT, reply_markup=stats_menu_kb(), parse_mode="HTML")


async def cb_stats_menu(query: types.CallbackQuery):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if user and user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await query.message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        await query.answer()
        return
    session.close()
    await query.message.edit_text(STATS_MENU_TEXT, parse_mode="HTML")
    await query.message.edit_reply_markup(reply_markup=stats_menu_inline_kb())
    await query.answer()

async def cmd_stats(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if user and user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    session.close()
    await message.answer(
        STATS_CHOOSE_PERIOD, reply_markup=stats_period_kb()
    )

async def cb_stats(query: types.CallbackQuery):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        await query.answer(STATS_NO_DATA, show_alert=True)
        session.close()
        return
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await query.message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        await query.answer()
        return
    period = query.data.split(':', 1)[1]
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


async def cb_report_day(query: types.CallbackQuery):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        await query.message.edit_text(STATS_NO_DATA)
        await query.answer()
        session.close()
        return
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await query.message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        await query.answer()
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
        new_text = REPORT_EMPTY
        if query.message.text != new_text:
            await query.message.edit_text(new_text)
        builder = InlineKeyboardBuilder()
        builder.button(text=BTN_BACK, callback_data="stats_menu")
        builder.adjust(1)
        await query.message.edit_reply_markup(reply_markup=builder.as_markup())
        await query.answer()
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

    new_text = "\n".join(lines)
    if query.message.text != new_text:
        await query.message.edit_text(new_text)
    # Show only a back button leading to the stats menu
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="stats_menu")
    builder.adjust(1)
    await query.message.edit_reply_markup(reply_markup=builder.as_markup())
    await query.answer()


async def report_day(message: types.Message):
    """Send today's meal report with totals and list."""
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        await message.answer(STATS_NO_DATA, reply_markup=main_menu_kb())
        session.close()
        return
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
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
        builder = InlineKeyboardBuilder()
        builder.button(text=BTN_BACK, callback_data="stats_menu")
        builder.adjust(1)
        await message.answer(
            REPORT_EMPTY,
            reply_markup=builder.as_markup(),
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

    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="stats_menu")
    builder.adjust(1)
    await message.answer("\n".join(lines), reply_markup=builder.as_markup())


async def cb_my_meals(query: types.CallbackQuery):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if user and user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await query.message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        await query.answer()
        return
    session.close()
    text, markup = build_history_text(query.from_user.id, 0, header=True)
    await query.message.edit_text(text)
    await query.message.edit_reply_markup(reply_markup=markup)
    await query.answer()


def register(dp: Dispatcher):
    dp.message.register(cmd_stats, Command('stats'))
    dp.message.register(show_stats_menu, F.text == BTN_STATS)
    dp.message.register(report_day, F.text == BTN_REPORT_DAY)
    dp.callback_query.register(cb_stats_menu, F.data == 'stats_menu')
    dp.callback_query.register(cb_report_day, F.data == 'report_day')
    dp.callback_query.register(cb_my_meals, F.data == 'my_meals')
    dp.callback_query.register(cb_stats, F.data.startswith('stats:'))

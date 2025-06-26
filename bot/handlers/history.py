from aiogram import types, Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime, timedelta
from ..database import SessionLocal, Meal, User
from ..keyboards import back_menu_kb, history_nav_kb
from ..texts import (
    MONTHS_RU,
    HISTORY_HEADER,
    HISTORY_NO_MEALS,
    HISTORY_DAY_HEADER,
    HISTORY_LINE_CAL,
    HISTORY_LINE_P,
    HISTORY_LINE_F,
    HISTORY_LINE_C,
    BTN_LEFT_HISTORY,
    BTN_RIGHT_HISTORY,
    BTN_MY_MEALS,
)

async def send_history(bot: Bot, user_id: int, chat_id: int, offset: int, header: bool = False):
    """Send totals for two days starting from offset."""
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    text_lines = [HISTORY_HEADER, ""] if header else []
    if not user:
        for i in range(2):
            day = datetime.utcnow().date() - timedelta(days=offset + i)
            month = MONTHS_RU.get(day.month, day.strftime('%B'))
            text_lines.append(HISTORY_DAY_HEADER.format(day=day.day, month=month))
            text_lines.append(HISTORY_NO_MEALS)
            text_lines.append("")
        await bot.send_message(chat_id, "\n".join(text_lines), reply_markup=history_nav_kb(offset, 1))
        session.close()
        return
    
    if not header:
        text_lines = []
    any_data = False
    for i in range(2):
        day = datetime.utcnow().date() - timedelta(days=offset + i)
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        meals = (
            session.query(Meal)
            .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
            .all()
        )
        month = MONTHS_RU.get(day.month, day.strftime('%B'))
        text_lines.append(HISTORY_DAY_HEADER.format(day=day.day, month=month))
        if not meals:
            text_lines.append(HISTORY_NO_MEALS)
            text_lines.append("")
            continue
        any_data = True
        totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
        for m in meals:
            totals["calories"] += m.calories
            totals["protein"] += m.protein
            totals["fat"] += m.fat
            totals["carbs"] += m.carbs
        text_lines.extend(
            [
                HISTORY_LINE_CAL.format(cal=int(totals['calories'])),
                HISTORY_LINE_P.format(protein=int(totals['protein'])),
                HISTORY_LINE_F.format(fat=int(totals['fat'])),
                HISTORY_LINE_C.format(carbs=int(totals['carbs'])),
                "",
            ]
        )
    session.close()
    builder = InlineKeyboardBuilder()
    count = 1
    builder.button(text=BTN_LEFT_HISTORY, callback_data=f"hist:{offset+1}")
    if offset > 0:
        builder.button(text=BTN_RIGHT_HISTORY, callback_data=f"hist:{offset-1}")
        count += 1
    builder.adjust(count)
    await bot.send_message(chat_id, "\n".join(text_lines), reply_markup=builder.as_markup())

async def cmd_history(message: types.Message):
    await send_history(
        message.bot,
        message.from_user.id,
        message.chat.id,
        0,
        header=True,
    )

async def cb_history(query: types.CallbackQuery):
    offset = int(query.data.split(':', 1)[1])
    await query.message.delete()
    await send_history(query.bot, query.from_user.id, query.message.chat.id, offset, header=True)
    await query.answer()


def register(dp: Dispatcher):
    dp.message.register(cmd_history, Command('history'))
    dp.message.register(cmd_history, F.text == BTN_MY_MEALS)
    dp.callback_query.register(cb_history, F.data.startswith('hist:'))

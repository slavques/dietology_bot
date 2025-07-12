from aiogram import types, Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime, timedelta
from ..database import SessionLocal, Meal, User
from ..keyboards import history_nav_kb
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

def build_history_text(user_id: int, offset: int, header: bool = False):
    """Prepare history text and navigation keyboard."""
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
        markup = history_nav_kb(offset, include_back=True)
        session.close()
        return "\n".join(text_lines), markup
    
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
                HISTORY_LINE_CAL.format(cal=round(totals['calories'], 1)),
                HISTORY_LINE_P.format(protein=round(totals['protein'], 1)),
                HISTORY_LINE_F.format(fat=round(totals['fat'], 1)),
                HISTORY_LINE_C.format(carbs=round(totals['carbs'], 1)),
                "",
            ]
        )
    session.close()
    markup = history_nav_kb(offset, include_back=True)
    return "\n".join(text_lines), markup


async def send_history(bot: Bot, user_id: int, chat_id: int, offset: int, header: bool = False):
    text, markup = build_history_text(user_id, offset, header)
    await bot.send_message(chat_id, text, reply_markup=markup)

async def cmd_history(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if user and user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    session.close()
    await send_history(
        message.bot,
        message.from_user.id,
        message.chat.id,
        0,
        header=True,
    )

async def cb_history(query: types.CallbackQuery):
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
    offset = int(query.data.split(':', 1)[1])
    text, markup = build_history_text(query.from_user.id, offset, header=True)
    await query.message.edit_text(text)
    await query.message.edit_reply_markup(reply_markup=markup)
    await query.answer()


def register(dp: Dispatcher):
    dp.message.register(cmd_history, Command('history'))
    dp.message.register(cmd_history, F.text == BTN_MY_MEALS)
    dp.callback_query.register(cb_history, F.data.startswith('hist:'))

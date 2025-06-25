from aiogram import types, Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime, timedelta
from ..database import SessionLocal, Meal, User
from ..keyboards import back_menu_kb, history_nav_kb
from ..texts import MONTHS_RU

async def send_history(bot: Bot, user_id: int, chat_id: int, offset: int, header: bool = False):
    """Send totals for two days starting from offset."""
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    text_lines = ["📊 Мои приёмы", ""] if header else []
    if not user:
        for i in range(2):
            day = datetime.utcnow().date() - timedelta(days=offset + i)
            month = MONTHS_RU.get(day.month, day.strftime('%B'))
            text_lines.append(f"📊 Итого за {day.day} {month}:")
            text_lines.append("Нет ни одного приёма пищи.")
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
        text_lines.append(f"📊 Итого за {day.day} {month}:")
        if not meals:
            text_lines.append("Нет ни одного приёма пищи.")
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
                f"🔥 Калории: {int(totals['calories'])} ккал",
                f"• Белки: {int(totals['protein'])} г",
                f"• Жиры: {int(totals['fat'])} г",
                f"• Углеводы: {int(totals['carbs'])} г",
                "",
            ]
        )
    session.close()
    builder = InlineKeyboardBuilder()
    count = 1
    builder.button(text="⬅️ Записи ранее", callback_data=f"hist:{offset+1}")
    if offset > 0:
        builder.button(text="Записи позже ➡️", callback_data=f"hist:{offset-1}")
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
    dp.message.register(cmd_history, F.text == "📊 Мои приёмы")
    dp.callback_query.register(cb_history, F.data.startswith('hist:'))

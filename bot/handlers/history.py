from aiogram import types, Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime, timedelta
from ..database import SessionLocal, Meal, User
from ..keyboards import back_menu_kb

async def send_history(bot: Bot, user_id: int, chat_id: int, offset: int):
    """Send totals for two days starting from offset."""
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        await bot.send_message(chat_id, "История пуста.")
        session.close()
        return

    text_lines = ["\ud83d\udcca \u041c\u043e\u0438 \u043f\u0440\u0438\u0451\u043c\u044b", ""]
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
        if not meals:
            continue
        any_data = True
        totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
        for m in meals:
            totals["calories"] += m.calories
            totals["protein"] += m.protein
            totals["fat"] += m.fat
            totals["carbs"] += m.carbs
        text_lines.append(
            f"\ud83d\udcca \u0418\u0442\u043e\u0433\u043e \u0437\u0430 {day.day} {day.strftime('%B')}:"\
        )
        text_lines.extend(
            [
                f"\u2022 \ud83d\udd25 \u041a\u0430\u043b\u043e\u0440\u0438\u0438: {int(totals['calories'])} \u043a\u043a\u0430\u043b",
                f"\u2022 \u0411\u0435\u043b\u043a\u0438: {int(totals['protein'])} \u0433",
                f"\u2022 \u0416\u0438\u0440\u044b: {int(totals['fat'])} \u0433",
                f"\u2022 \u0423\u0433\u043B\u0435\u0432\u043E\u0434\u044B: {int(totals['carbs'])} \u0433",
                "",
            ]
        )
    session.close()
    if not any_data:
        await bot.send_message(chat_id, "\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u043F\u0443\u0441\u0442\u0430.")
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="\u2b05\ufe0f \u0417\u0430\u043f\u0438\u0441\u0438 \u0440\u0430\u043d\u0435\u0435", callback_data=f"hist:{offset+1}")
    if offset > 0:
        builder.button(text="\u0417\u0430\u043f\u0438\u0441\u0438 \u043f\u043e\u0437\u0436\u0435 \u27a1\ufe0f", callback_data=f"hist:{offset-1}")
    builder.adjust(len(builder.buttons))
    await bot.send_message(chat_id, "\n".join(text_lines), reply_markup=builder.as_markup())

async def cmd_history(message: types.Message):
    await message.answer("\ud83d\udcca \u041c\u043e\u0438 \u043f\u0440\u0438\u0451\u043c\u044b", reply_markup=back_menu_kb())
    await send_history(message.bot, message.from_user.id, message.chat.id, 0)

async def cb_history(query: types.CallbackQuery):
    offset = int(query.data.split(':', 1)[1])
    await query.message.delete()
    await send_history(query.bot, query.from_user.id, query.message.chat.id, offset)
    await query.answer()


def register(dp: Dispatcher):
    dp.message.register(cmd_history, Command('history'))
    dp.message.register(cmd_history, F.text == "\U0001F4CA \u041C\u043E\u0438 \u043F\u0440\u0438\u0451\u043C\u044B")
    dp.callback_query.register(cb_history, F.data.startswith('hist:'))

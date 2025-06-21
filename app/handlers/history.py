from aiogram import types
from aiogram.dispatcher import Dispatcher

from ..db import SessionLocal
from ..models import User, Meal
from ..utils import format_meal_message


def send_history(user_id: int, chat_id: int, offset: int, bot):
    session = SessionLocal()
    q = session.query(Meal).join(User).filter(User.telegram_id == user_id).order_by(Meal.timestamp.desc())
    total = q.count()
    meal = q.offset(offset).limit(1).first()
    session.close()
    if not meal:
        return bot.send_message(chat_id, "История пуста.")
    markup = types.InlineKeyboardMarkup()
    if offset > 0:
        markup.insert(types.InlineKeyboardButton("\u2190", callback_data=f"hist:{offset-1}"))
    if offset < total - 1:
        markup.insert(types.InlineKeyboardButton("\u2192", callback_data=f"hist:{offset+1}"))
    return bot.send_message(
        chat_id,
        format_meal_message(
            meal.name,
            meal.serving,
            {
                "calories": meal.calories,
                "protein": meal.protein,
                "fat": meal.fat,
                "carbs": meal.carbs,
            },
        ),
        reply_markup=markup,
    )


def setup(dp: Dispatcher):
    bot = dp.bot

    @dp.message_handler(commands=['history'])
    async def cmd_history(message: types.Message):
        await send_history(message.from_user.id, message.chat.id, 0, bot)

    @dp.callback_query_handler(lambda c: c.data.startswith("hist:"))
    async def cb_history(query: types.CallbackQuery):
        offset = int(query.data.split(":", 1)[1])
        await query.message.delete()
        await send_history(query.from_user.id, query.message.chat.id, offset, bot)
        await query.answer()

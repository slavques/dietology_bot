from aiogram import types, Dispatcher, Bot, F
from aiogram.filters import Command

from ..database import SessionLocal, Meal, User
from ..utils import format_meal_message
from ..keyboards import history_nav_kb

async def send_history(bot: Bot, user_id: int, chat_id: int, offset: int):
    session = SessionLocal()
    q = session.query(Meal).join(User).filter(User.telegram_id == user_id).order_by(Meal.timestamp.desc())
    total = q.count()
    meal = q.offset(offset).limit(1).first()
    session.close()
    if not meal:
        await bot.send_message(chat_id, "История пуста.")
        return
    await bot.send_message(
        chat_id,
        format_meal_message(
            meal.name,
            meal.serving,
            {
                'calories': meal.calories,
                'protein': meal.protein,
                'fat': meal.fat,
                'carbs': meal.carbs,
            },
        ),
        reply_markup=history_nav_kb(offset, total)
    )

async def cmd_history(message: types.Message):
    await send_history(message.bot, message.from_user.id, message.chat.id, 0)

async def cb_history(query: types.CallbackQuery):
    offset = int(query.data.split(':', 1)[1])
    await query.message.delete()
    await send_history(query.bot, query.from_user.id, query.message.chat.id, offset)
    await query.answer()


def register(dp: Dispatcher):
    dp.message.register(cmd_history, Command('history'))
    dp.callback_query.register(cb_history, F.data.startswith('hist:'))

from aiogram import types
from aiogram.dispatcher import Dispatcher

from ..db import SessionLocal
from ..models import User


def setup(dp: Dispatcher):
    @dp.message_handler(commands=['start'])
    async def cmd_start(message: types.Message):
        session = SessionLocal()
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            user = User(telegram_id=message.from_user.id)
            session.add(user)
            session.commit()
        session.close()
        await message.reply("Привет! Отправь фото блюда, и я рассчитаю КБЖУ.")

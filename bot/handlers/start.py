from aiogram import types, Dispatcher
from aiogram.filters import Command
from ..database import SessionLocal, User

async def cmd_start(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        user = User(telegram_id=message.from_user.id)
        session.add(user)
        session.commit()
    session.close()
    await message.reply("Привет! Отправь фото блюда, и я рассчитаю КБЖУ.")


def register(dp: Dispatcher):
    dp.message.register(cmd_start, Command('start'))

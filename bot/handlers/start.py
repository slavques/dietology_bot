from aiogram import types, Dispatcher
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..keyboards import main_menu_kb

async def cmd_start(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        user = User(telegram_id=message.from_user.id)
        session.add(user)
        session.commit()
    session.close()
    text = (
        "Я — твой AI-диетолог 🧠\n\n"
        "Загрузи фото еды, и за секунды получишь:\n"
        "— Калории\n"
        "— Белки, жиры, углеводы\n"
        "— Быстрый отчёт в историю\n\n"
        "🔍 Готов? Отправь фото."
    )
    await message.answer(text, reply_markup=main_menu_kb())


async def back_to_menu(message: types.Message):
    """Return user to the main menu."""
    await message.answer("Выберите действие:", reply_markup=main_menu_kb())


def register(dp: Dispatcher):
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(
        back_to_menu,
        lambda m: m.text == "\U0001F951 \u0413\u043B\u0430\u0432\u043D\u043E\u0435 \u043C\u0435\u043D\u044E",
    )
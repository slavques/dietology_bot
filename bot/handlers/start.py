from aiogram import types, Dispatcher
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..keyboards import main_menu_kb

WELCOME_TEXT = (
    "Я — твой AI-диетолог 🧠\n\n"
    "Загрузи фото еды, и за секунды получишь:\n"
    "— Калории\n"
    "— Белки, жиры, углеводы\n"
    "— Быстрый отчёт в историю\n\n"
    "🔍 Готов? Отправь фото."
)

async def cmd_start(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        user = User(telegram_id=message.from_user.id)
        session.add(user)
        session.commit()
    session.close()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


async def back_to_menu(message: types.Message):
    """Return user to the main menu."""
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


def register(dp: Dispatcher):
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(
        back_to_menu,
        lambda m: m.text == "🥑 Главное меню",
    )

from aiogram import types, Dispatcher
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..subscriptions import ensure_user
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
    ensure_user(session, message.from_user.id)
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

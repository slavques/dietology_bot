from aiogram import types, Dispatcher
from aiogram.filters import Command

from ..database import SessionLocal, User
from ..subscriptions import ensure_user, days_left, update_limits
from ..keyboards import main_menu_kb


BASE_TEXT = (
    "Я — твой AI-диетолог 🧠\n\n"
    "Загрузи фото еды, и за секунды получишь:\n"
    "— Калории\n"
    "— Белки, жиры, углеводы\n"
    "— Быстрый отчёт в историю\n\n"
    "🔍 Готов? Отправь фото."
)


def get_welcome_text(user: User) -> str:
    update_limits(user)
    if user.grade == "free":
        remaining = max(user.request_limit - user.requests_used, 0)
        extra = f"(осталось бесплатных запросов: {remaining})"
    else:
        days = days_left(user) or 0
        extra = f"(осталось дней подписки: {days})"
    return f"{BASE_TEXT}\n{extra}"

async def cmd_start(message: types.Message):
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    text = get_welcome_text(user)
    session.commit()
    session.close()
    await message.answer(text, reply_markup=main_menu_kb())


async def back_to_menu(message: types.Message):
    """Return user to the main menu."""
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    text = get_welcome_text(user)
    session.commit()
    session.close()
    await message.answer(text, reply_markup=main_menu_kb())


def register(dp: Dispatcher):
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(
        back_to_menu,
        lambda m: m.text == "🥑 Главное меню",
    )

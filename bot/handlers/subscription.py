from datetime import datetime
from aiogram import types, Dispatcher, F
from aiogram.filters import Command

from ..database import SessionLocal
from ..subscriptions import ensure_user, process_payment_success, _daily_check

SUCCESS_CMD = "success1467"
REFUSED_CMD = "refused1467"
NOTIFY_CMD = "notify1467"


async def cb_pay(query: types.CallbackQuery):
    """Show payment instructions."""
    await query.message.answer(
        "Чтобы оформить подписку, используйте команду /success1467 или свяжитесь с поддержкой."
    )
    await query.answer()

async def cmd_success(message: types.Message):
    if not message.text.startswith(f"/{SUCCESS_CMD}"):
        return
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    process_payment_success(session, user)
    session.close()
    await message.answer("Оплата принята. Подписка активирована.")

async def cmd_refused(message: types.Message):
    if not message.text.startswith(f"/{REFUSED_CMD}"):
        return
    await message.answer("Оплата отменена.")


async def cmd_notify(message: types.Message):
    if not message.text.startswith(f"/{NOTIFY_CMD}"):
        return
    await _daily_check(message.bot)
    await message.answer("Уведомления отправлены")


def register(dp: Dispatcher):
    dp.message.register(cmd_success, Command(SUCCESS_CMD))
    dp.message.register(cmd_refused, Command(REFUSED_CMD))
    dp.message.register(cmd_notify, Command(NOTIFY_CMD))
    dp.callback_query.register(cb_pay, F.data == "pay")

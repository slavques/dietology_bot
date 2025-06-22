from datetime import datetime
from aiogram import types, Dispatcher
from aiogram.filters import Command

from ..database import SessionLocal
from ..subscriptions import ensure_user, process_payment_success

SUCCESS_CMD = "success1467"
REFUSED_CMD = "refused1467"

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


def register(dp: Dispatcher):
    dp.message.register(cmd_success, Command(SUCCESS_CMD))
    dp.message.register(cmd_refused, Command(REFUSED_CMD))

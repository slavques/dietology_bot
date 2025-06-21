from aiogram import types
from aiogram.types import ErrorEvent
import logging

async def handle_error(event: ErrorEvent) -> bool:
    """Send a generic message to the user when any handler fails."""
    logging.exception("Handler error", exc_info=event.exception)
    update = event.update
    if isinstance(update, types.Message):
        await update.answer("Произошла ошибка на сервере, попробуйте позже.")
    elif isinstance(update, types.CallbackQuery):
        await update.message.answer("Произошла ошибка на сервере, попробуйте позже.")
    return True

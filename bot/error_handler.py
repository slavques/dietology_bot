from aiogram import types
from aiogram.types import ErrorEvent
from .texts import SERVER_ERROR
import logging

async def handle_error(event: ErrorEvent) -> bool:
    """Send a generic message to the user when any handler fails."""
    logging.exception("Handler error", exc_info=event.exception)
    update = event.update
    if isinstance(update, types.Message):
        await update.answer(SERVER_ERROR)
    elif isinstance(update, types.CallbackQuery):
        await update.message.answer(SERVER_ERROR)
    return True

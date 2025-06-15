from aiogram import types

async def handle_error(update: types.Update, exception: Exception) -> bool:
    if isinstance(update, types.Message):
        await update.answer("Произошла ошибка на сервере, попробуйте позже.")
    elif isinstance(update, types.CallbackQuery):
        await update.message.answer("Произошла ошибка на сервере, попробуйте позже.")
    return True

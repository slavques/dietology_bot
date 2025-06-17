from aiogram import types, Dispatcher, F
from ..keyboards import back_menu_kb

FAQ_TEXT = (
    "Часто задаваемые вопросы:\n"
    "1. Как пользоваться ботом? Просто отправьте фото блюда!\n"
    "2. Как посчитать КБЖУ вручную? Введите название и вес."
)

async def cmd_faq(message: types.Message):
    await message.answer(FAQ_TEXT, reply_markup=back_menu_kb())


def register(dp: Dispatcher):
    dp.message.register(cmd_faq, F.text == "\u2753 \u0427\u0430\u0412\u041E")

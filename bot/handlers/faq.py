from ..settings import SUPPORT_HANDLE, FAQ_LINK
from aiogram import types, Dispatcher, F
from ..keyboards import back_menu_kb
from ..texts import FAQ_TEXT

async def cmd_faq(message: types.Message):
    await message.answer(
        FAQ_TEXT.format(link=FAQ_LINK, support=SUPPORT_HANDLE),
        reply_markup=back_menu_kb(),
        parse_mode="HTML",
    )


def register(dp: Dispatcher):
    dp.message.register(cmd_faq, F.text == "❓ ЧаВО")

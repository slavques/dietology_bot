from ..settings import SUPPORT_HANDLE, FAQ_LINK
from aiogram import types, Dispatcher, F
from ..keyboards import back_menu_kb

FAQ_TEXT = (
    "❓ Что, как и почему?\n"
    "Мы собрали все частые вопросы в одной статье: от распознавания еды до подписки.\n\n"
    "👇 Загляни в ЧаВо — там всё просто\n"
    f"[❓ЧаВо]({FAQ_LINK})\n\n"
    f"📬 Есть вопросы? Напишите нам: {SUPPORT_HANDLE}"
)

async def cmd_faq(message: types.Message):
    await message.answer(FAQ_TEXT, reply_markup=back_menu_kb(), parse_mode="Markdown")


def register(dp: Dispatcher):
    dp.message.register(cmd_faq, F.text == "❓ ЧаВО")

from ..settings import SUPPORT_HANDLE, FAQ_LINK
from aiogram import types, Dispatcher, F
from ..keyboards import back_menu_kb

<<<<<<< codex/fix-telegrambadrequest-in-faq-handler
FAQ_TEXT = f"""
❓ Что, как и почему?
Мы собрали все частые вопросы в одной статье: от распознавания еды до подписки.

👇 Загляни в ЧаВо — там всё просто
❓<a href="{FAQ_LINK}">ЧаВо</a>

📬 Есть вопросы? Напишите нам: {SUPPORT_HANDLE}
"""
=======
FAQ_TEXT = (
    "❓ Что, как и почему?\n"
    "Мы собрали все частые вопросы в одной статье: от распознавания еды до подписки.\n\n"
    "👇 Загляни в ЧаВо — там всё просто\n"
<<<<<<< codex/fix-telegrambadrequest-in-faq-handler
    f'❓<a href="{FAQ_LINK}">ЧаВо</a>\n\n'
=======
    f'<a href="{FAQ_LINK}">❓ЧаВо</a>\n\n'
>>>>>>> dev
    f"📬 Есть вопросы? Напишите нам: {SUPPORT_HANDLE}"
)
>>>>>>> dev

async def cmd_faq(message: types.Message):
    await message.answer(FAQ_TEXT, reply_markup=back_menu_kb(), parse_mode="HTML")


def register(dp: Dispatcher):
    dp.message.register(cmd_faq, F.text == "❓ ЧаВО")

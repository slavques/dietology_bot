from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..database import SessionLocal, User
from ..states import AdminState
from ..config import ADMIN_COMMAND
from ..texts import (
    BTN_BROADCAST,
    BTN_BACK,
    ADMIN_MODE,
    ADMIN_UNAVAILABLE,
    BROADCAST_PROMPT,
    BROADCAST_ERROR,
    BROADCAST_DONE,
)

admins = set()


def admin_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BROADCAST, callback_data="admin:broadcast")
    builder.adjust(1)
    return builder.as_markup()


def admin_back_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


async def admin_login(message: types.Message):
    if message.text != f"/{ADMIN_COMMAND}":
        return
    admins.add(message.from_user.id)
    await message.answer(ADMIN_MODE, reply_markup=admin_menu_kb())


async def admin_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_MODE, reply_markup=admin_menu_kb())
    await query.answer()


async def admin_broadcast_prompt(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_broadcast)
    await query.message.edit_text(BROADCAST_PROMPT, reply_markup=admin_back_kb())
    await query.answer()


async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    text = message.text
    session = SessionLocal()
    users = session.query(User).all()
    error = False
    for u in users:
        try:
            await message.bot.send_message(u.telegram_id, text)
        except Exception:
            error = True
    session.close()
    await message.answer(
        BROADCAST_ERROR if error else BROADCAST_DONE,
        reply_markup=admin_menu_kb(),
    )
    await state.clear()


def register(dp: Dispatcher):
    dp.message.register(admin_login, F.text.startswith(f"/{ADMIN_COMMAND}"))
    dp.callback_query.register(admin_broadcast_prompt, F.data == "admin:broadcast")
    dp.callback_query.register(admin_menu, F.data == "admin:menu")
    dp.message.register(process_broadcast, AdminState.waiting_broadcast, F.text)

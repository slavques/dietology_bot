from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from ..database import SessionLocal, User
from ..states import AdminState
from ..config import ADMIN_COMMAND, ADMIN_PASSWORD
from ..texts import (
    BTN_BROADCAST,
    BTN_BACK,
    BTN_DAYS,
    BTN_ONE,
    BTN_ALL,
    BTN_BLOCK,
    BTN_STATS_ADMIN,
    ADMIN_MODE,
    ADMIN_UNAVAILABLE,
    BROADCAST_PROMPT,
    BROADCAST_ERROR,
    BROADCAST_DONE,
    ADMIN_CHOOSE_ACTION,
    ADMIN_ENTER_ID,
    ADMIN_ENTER_DAYS,
    ADMIN_DAYS_DONE,
    ADMIN_BLOCK_DONE,
    ADMIN_STATS,
)

admins = set()


def admin_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BROADCAST, callback_data="admin:broadcast")
    builder.button(text=BTN_DAYS, callback_data="admin:days")
    builder.button(text=BTN_BLOCK, callback_data="admin:block")
    builder.button(text=BTN_STATS_ADMIN, callback_data="admin:stats")
    builder.adjust(1)
    return builder.as_markup()


def admin_back_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def days_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_ONE, callback_data="admin:days_one")
    builder.button(text=BTN_ALL, callback_data="admin:days_all")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


async def admin_login(message: types.Message):
    if not message.text.startswith(f"/{ADMIN_COMMAND}"):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or parts[1] != ADMIN_PASSWORD:
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


async def admin_days_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=days_menu_kb())
    await query.answer()


async def admin_days_one(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_user_id)
    await query.message.edit_text(ADMIN_ENTER_ID, reply_markup=admin_back_kb())
    await query.answer()


async def admin_days_all(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_days_all)
    await query.message.edit_text(ADMIN_ENTER_DAYS, reply_markup=admin_back_kb())
    await query.answer()


async def admin_block_prompt(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_block_id)
    await query.message.edit_text(ADMIN_ENTER_ID, reply_markup=admin_back_kb())
    await query.answer()


async def admin_stats(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    session = SessionLocal()
    now = datetime.utcnow()
    total = session.query(User).count()
    paid = session.query(User).filter(User.grade == "paid", User.period_end > now).count()
    pro = session.query(User).filter(User.grade == "pro", User.period_end > now).count()
    used = session.query(User).filter(User.grade == "free", User.requests_used > 0).count()
    session.close()
    text = ADMIN_STATS.format(total=total, paid=paid, pro=pro, used=used)
    await query.message.edit_text(text, reply_markup=admin_menu_kb())
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


async def process_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await state.update_data(target_id=message.text.strip())
    await state.set_state(AdminState.waiting_days)
    await message.answer(ADMIN_ENTER_DAYS, reply_markup=admin_back_kb())


async def process_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    data = await state.get_data()
    target = data.get("target_id")
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_DAYS)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=int(target)).first()
    if user:
        from ..subscriptions import add_subscription_days

        add_subscription_days(session, user, days)
    session.close()
    await message.answer(ADMIN_DAYS_DONE, reply_markup=admin_menu_kb())
    await state.clear()


async def process_days_all(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_DAYS)
        return
    session = SessionLocal()
    now = datetime.utcnow()
    from ..subscriptions import add_subscription_days

    users = (
        session.query(User)
        .filter(User.grade.in_(["paid", "pro"]), User.period_end > now)
        .all()
    )
    for u in users:
        add_subscription_days(session, u, days)
    session.close()
    await message.answer(ADMIN_DAYS_DONE, reply_markup=admin_menu_kb())
    await state.clear()


async def process_block(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        target = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_ID)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=target).first()
    if user:
        user.blocked = True
        session.commit()
    session.close()
    await message.answer(ADMIN_BLOCK_DONE, reply_markup=admin_menu_kb())
    await state.clear()


def register(dp: Dispatcher):
    dp.message.register(admin_login, F.text.startswith(f"/{ADMIN_COMMAND}"))
    dp.callback_query.register(admin_broadcast_prompt, F.data == "admin:broadcast")
    dp.callback_query.register(admin_days_menu, F.data == "admin:days")
    dp.callback_query.register(admin_days_one, F.data == "admin:days_one")
    dp.callback_query.register(admin_days_all, F.data == "admin:days_all")
    dp.callback_query.register(admin_block_prompt, F.data == "admin:block")
    dp.callback_query.register(admin_stats, F.data == "admin:stats")
    dp.callback_query.register(admin_menu, F.data == "admin:menu")
    dp.message.register(process_broadcast, AdminState.waiting_broadcast, F.text)
    dp.message.register(process_user_id, AdminState.waiting_user_id, F.text)
    dp.message.register(process_days, AdminState.waiting_days, F.text)
    dp.message.register(process_days_all, AdminState.waiting_days_all, F.text)
    dp.message.register(process_block, AdminState.waiting_block_id, F.text)

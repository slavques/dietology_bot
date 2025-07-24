from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from datetime import datetime, timedelta

from ..database import SessionLocal
from ..subscriptions import ensure_user
from ..keyboards import (
    settings_menu_kb,
    reminders_main_kb,
    reminders_settings_kb,
    back_inline_kb,
)
from ..texts import (
    TZ_PROMPT,
    TIME_CURRENT,
    REMINDER_ON,
    REMINDER_OFF,
    SET_TIME_PROMPT,
    BTN_REMINDERS,
    BTN_MORNING,
    BTN_DAY_REM,
    BTN_EVENING,
    SETTINGS_TITLE,
)
from ..states import ReminderState


async def open_settings(query: types.CallbackQuery):
    """Show main settings menu."""
    await query.message.edit_text(SETTINGS_TITLE, reply_markup=settings_menu_kb())
    await query.answer()


async def open_reminders(query: types.CallbackQuery, state: FSMContext):
    """Entry point for reminder settings."""
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    if user.timezone is None:
        utc = datetime.utcnow().strftime("%H:%M")
        await query.message.edit_text(
            TZ_PROMPT.format(utc_time=utc), reply_markup=back_inline_kb()
        )
        await state.set_state(ReminderState.waiting_timezone)
    else:
        local = (datetime.utcnow() + timedelta(minutes=user.timezone)).strftime("%H:%M")
        await query.message.edit_text(
            TIME_CURRENT.format(local_time=local),
            reply_markup=reminders_main_kb(user),
        )
    await query.answer()
    session.close()


async def process_timezone(message: types.Message, state: FSMContext):
    """Handle user local time to determine timezone."""
    try:
        parts = message.text.strip().split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
    except Exception:
        await message.answer("Неверный формат времени. Попробуйте ещё раз 10:00")
        return
    user_time = hours * 60 + minutes
    utc_now = datetime.utcnow()
    server_minutes = utc_now.hour * 60 + utc_now.minute
    diff = user_time - server_minutes
    if diff <= -720:
        diff += 1440
    if diff >= 720:
        diff -= 1440
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    user.timezone = diff
    session.commit()
    await state.clear()
    await message.answer(
        TIME_CURRENT.format(local_time=message.text.strip()),
        reply_markup=reminders_main_kb(user),
    )
    session.close()


async def toggle(query: types.CallbackQuery, field: str):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    value = getattr(user, field)
    setattr(user, field, not value)
    session.commit()
    text = (
        REMINDER_ON.format(name=query.data.split('_')[1])
        if not value
        else REMINDER_OFF.format(name=query.data.split('_')[1])
    )
    await query.message.edit_reply_markup(reminders_main_kb(user))
    await query.answer(text, show_alert=False)
    session.close()


async def open_reminder_settings(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    await query.message.edit_reply_markup(reminders_settings_kb(user))
    await query.answer()
    session.close()


async def set_time_prompt(query: types.CallbackQuery, state: FSMContext, field: str, name: str):
    await query.message.answer(SET_TIME_PROMPT.format(name=name))
    await state.set_state(getattr(ReminderState, field))
    await query.answer()


async def process_time(message: types.Message, state: FSMContext, field: str, name: str):
    try:
        parts = message.text.strip().split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
    except Exception:
        await message.answer("Неверный формат времени. Попробуйте ещё раз 10:00")
        return
    time_str = f"{hours:02d}:{minutes:02d}"
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    setattr(user, field, time_str)
    session.commit()
    await message.answer(REMINDER_ON.format(name=name))
    await message.answer(
        TIME_CURRENT.format(
            local_time=(
                datetime.utcnow() + timedelta(minutes=user.timezone or 0)
            ).strftime("%H:%M")
        ),
        reply_markup=reminders_settings_kb(user),
    )
    await state.clear()
    session.close()


def register(dp: Dispatcher):
    dp.callback_query.register(open_settings, F.data == "settings")
    dp.callback_query.register(
        open_reminders,
        F.data.in_(["reminders", "reminders_back", "update_tz"]),
    )
    dp.callback_query.register(open_reminder_settings, F.data == "reminder_settings")
    dp.callback_query.register(lambda q: toggle(q, "morning_enabled"), F.data == "toggle_morning")
    dp.callback_query.register(lambda q: toggle(q, "day_enabled"), F.data == "toggle_day")
    dp.callback_query.register(lambda q: toggle(q, "evening_enabled"), F.data == "toggle_evening")
    dp.callback_query.register(lambda q, st: set_time_prompt(q, st, "set_morning", BTN_MORNING), F.data == "set_morning")
    dp.callback_query.register(lambda q, st: set_time_prompt(q, st, "set_day", BTN_DAY_REM), F.data == "set_day")
    dp.callback_query.register(lambda q, st: set_time_prompt(q, st, "set_evening", BTN_EVENING), F.data == "set_evening")

    dp.message.register(process_timezone, StateFilter(ReminderState.waiting_timezone))
    dp.message.register(lambda m, st: process_time(m, st, "morning_time", BTN_MORNING), StateFilter(ReminderState.set_morning))
    dp.message.register(lambda m, st: process_time(m, st, "day_time", BTN_DAY_REM), StateFilter(ReminderState.set_day))
    dp.message.register(lambda m, st: process_time(m, st, "evening_time", BTN_EVENING), StateFilter(ReminderState.set_evening))

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
    back_to_reminder_settings_kb,
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
    if user.timezone is None or query.data == "update_tz":
        utc = datetime.utcnow().strftime("%H:%M")
        await query.message.edit_text(
            TZ_PROMPT.format(utc_time=utc), reply_markup=back_inline_kb()
        )
        await state.update_data(prompt_id=query.message.message_id)
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
        from ..texts import INVALID_TIME

        await message.answer(INVALID_TIME)
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
    data = await state.get_data()
    prompt_id = data.get("prompt_id")
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    if prompt_id:
        await message.bot.edit_message_text(
            TIME_CURRENT.format(local_time=message.text.strip()),
            chat_id=message.chat.id,
            message_id=prompt_id,
            reply_markup=reminders_main_kb(user),
        )
    else:
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
    await query.message.edit_reply_markup(
        reply_markup=reminders_main_kb(user)
    )
    await query.answer(text, show_alert=False)
    session.close()


async def open_reminder_settings(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    local = (datetime.utcnow() + timedelta(minutes=user.timezone or 0)).strftime("%H:%M")
    await query.message.edit_text(
        TIME_CURRENT.format(local_time=local),
        reply_markup=reminders_settings_kb(user),
    )
    await query.answer()
    session.close()


async def set_time_prompt(query: types.CallbackQuery, state: FSMContext, field: str, name: str):
    await query.message.edit_text(SET_TIME_PROMPT.format(name=name))
    await query.message.edit_reply_markup(reply_markup=back_to_reminder_settings_kb())
    await state.update_data(prompt_id=query.message.message_id)
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
        from ..texts import INVALID_TIME

        await message.answer(INVALID_TIME)
        return
    time_str = f"{hours:02d}:{minutes:02d}"
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    setattr(user, field, time_str)
    session.commit()
    data = await state.get_data()
    prompt_id = data.get("prompt_id")
    local_time = (
        datetime.utcnow() + timedelta(minutes=user.timezone or 0)
    ).strftime("%H:%M")
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    text = REMINDER_ON.format(name=name) + "\n" + TIME_CURRENT.format(local_time=local_time)
    if prompt_id:
        await message.bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=prompt_id,
            reply_markup=reminders_settings_kb(user),
        )
    else:
        await message.answer(text, reply_markup=reminders_settings_kb(user))
    session.close()


async def toggle_morning(query: types.CallbackQuery):
    """Toggle morning reminder."""
    await toggle(query, "morning_enabled")


async def toggle_day(query: types.CallbackQuery):
    """Toggle day reminder."""
    await toggle(query, "day_enabled")


async def toggle_evening(query: types.CallbackQuery):
    """Toggle evening reminder."""
    await toggle(query, "evening_enabled")


async def set_morning_prompt(query: types.CallbackQuery, state: FSMContext):
    await set_time_prompt(query, state, "set_morning", BTN_MORNING)


async def set_day_prompt(query: types.CallbackQuery, state: FSMContext):
    await set_time_prompt(query, state, "set_day", BTN_DAY_REM)


async def set_evening_prompt(query: types.CallbackQuery, state: FSMContext):
    await set_time_prompt(query, state, "set_evening", BTN_EVENING)


async def process_morning_time(message: types.Message, state: FSMContext):
    await process_time(message, state, "morning_time", BTN_MORNING)


async def process_day_time(message: types.Message, state: FSMContext):
    await process_time(message, state, "day_time", BTN_DAY_REM)


async def process_evening_time(message: types.Message, state: FSMContext):
    await process_time(message, state, "evening_time", BTN_EVENING)


def register(dp: Dispatcher):
    dp.callback_query.register(open_settings, F.data == "settings")
    dp.callback_query.register(
        open_reminders,
        F.data.in_(["reminders", "reminders_back", "update_tz"]),
    )
    dp.callback_query.register(open_reminder_settings, F.data == "reminder_settings")
    dp.callback_query.register(toggle_morning, F.data == "toggle_morning")
    dp.callback_query.register(toggle_day, F.data == "toggle_day")
    dp.callback_query.register(toggle_evening, F.data == "toggle_evening")
    dp.callback_query.register(set_morning_prompt, F.data == "set_morning")
    dp.callback_query.register(set_day_prompt, F.data == "set_day")
    dp.callback_query.register(set_evening_prompt, F.data == "set_evening")

    dp.message.register(process_timezone, StateFilter(ReminderState.waiting_timezone))
    dp.message.register(process_morning_time, StateFilter(ReminderState.set_morning))
    dp.message.register(process_day_time, StateFilter(ReminderState.set_day))
    dp.message.register(process_evening_time, StateFilter(ReminderState.set_evening))

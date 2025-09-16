import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import asyncio

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.handlers import goals  # noqa: E402
from bot.database import Goal  # noqa: E402
from bot import reminders  # noqa: E402
from bot.texts import (  # noqa: E402
    GOAL_REMINDERS_DISABLED,
    GOAL_INTRO_TEXT,
    GOAL_FREE_TRIAL_NOTE,
    GOAL_TRIAL_EXPIRED_NOTICE,
    GOAL_TRIAL_PAYWALL_TEXT,
)


@pytest.mark.asyncio
async def test_goal_save_enables_reminders_without_affecting_meal(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    user = MagicMock()
    user.goal = None
    user.morning_enabled = False
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))

    monkeypatch.setattr(goals, "goal_summary_text", lambda g: "summary")
    monkeypatch.setattr(goals, "goals_main_kb", MagicMock(return_value="kb"))

    message = MagicMock()
    message.edit_text = AsyncMock()

    query = MagicMock()
    query.from_user.id = 1
    query.message = message
    query.answer = AsyncMock()

    state = AsyncMock()
    state.get_data.return_value = {
        "calories": 1000,
        "protein": 100,
        "fat": 50,
        "carbs": 200,
        "gender": "male",
        "age": 30,
        "height": 170,
        "weight": 70,
        "activity": "low",
        "target": "maintain",
    }

    await goals.goal_confirm_save(query, state)

    assert isinstance(user.goal, Goal)
    assert user.goal.reminder_morning is True
    assert user.goal.reminder_evening is True
    assert user.morning_enabled is False
    session.commit.assert_called_once()
    message.edit_text.assert_awaited_once_with("summary", reply_markup="kb")
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_goal_reminders_uses_user_timezone(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    user = MagicMock()
    user.goal = Goal()
    user.timezone = 60  # +1 hour
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))

    monkeypatch.setattr(goals, "goal_reminders_settings_kb", MagicMock(return_value="kb"))

    message = MagicMock()
    message.edit_text = AsyncMock()

    query = MagicMock()
    query.from_user.id = 1
    query.message = message
    query.answer = AsyncMock()

    fake_now = datetime(2025, 1, 1, 12, 0)

    class DummyDatetime:
        @classmethod
        def utcnow(cls):
            return fake_now

    monkeypatch.setattr(goals, "datetime", DummyDatetime)

    await goals.goal_reminders(query)

    message.edit_text.assert_awaited_once()
    text_arg = message.edit_text.call_args[0][0]
    assert "13:00" in text_arg


@pytest.mark.asyncio
async def test_goal_time_prompts_timezone(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    user = MagicMock()
    user.goal = Goal()
    user.timezone = 0
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))

    message = MagicMock()
    message.message_id = 42
    message.edit_text = AsyncMock()

    query = MagicMock()
    query.from_user.id = 1
    query.message = message
    query.answer = AsyncMock()

    state = AsyncMock()

    fake_now = datetime(2025, 1, 1, 12, 0)

    class DummyDatetime:
        @classmethod
        def utcnow(cls):
            return fake_now

    monkeypatch.setattr(goals, "datetime", DummyDatetime)

    await goals.goal_time(query, state)

    message.edit_text.assert_awaited_once()
    text_arg = message.edit_text.call_args[0][0]
    assert "12:00" in text_arg
    state.update_data.assert_awaited_once_with(prompt_id=42)
    state.set_state.assert_awaited_once_with(goals.GoalReminderState.waiting_timezone)
    query.answer.assert_awaited_once()
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_goal_timezone_updates_and_returns(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    user = MagicMock()
    user.goal = Goal()
    user.timezone = 0
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))

    monkeypatch.setattr(goals, "goal_reminders_settings_kb", MagicMock(return_value="kb"))

    message = MagicMock()
    message.text = "13:00"
    message.chat.id = 1
    message.delete = AsyncMock()
    message.bot = MagicMock()
    message.bot.edit_message_text = AsyncMock()

    state = AsyncMock()
    state.get_data.return_value = {"prompt_id": 99}
    state.clear = AsyncMock()

    fake_now = datetime(2025, 1, 1, 12, 0)

    class DummyDatetime:
        @classmethod
        def utcnow(cls):
            return fake_now

    monkeypatch.setattr(goals, "datetime", DummyDatetime)

    await goals.goal_timezone(message, state)

    assert user.timezone == 60
    state.clear.assert_awaited_once()
    message.bot.edit_message_text.assert_awaited_once()
    text_arg = message.bot.edit_message_text.call_args[0][0]
    assert "13:00" in text_arg
    kwargs = message.bot.edit_message_text.call_args.kwargs
    assert kwargs.get("reply_markup") == "kb"
    session.commit.assert_called_once()
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_open_goals_shows_trial_note_for_free_user(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    user = MagicMock()
    user.goal = None
    user.grade = "free"
    user.goal_trial_start = None
    user.goal_trial_notified = False
    user.timezone = 0
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))

    update_limits_mock = MagicMock()
    monkeypatch.setattr(goals, "update_limits", update_limits_mock)

    monkeypatch.setattr(goals, "goal_start_kb", MagicMock(return_value="kb"))

    query = MagicMock()
    query.from_user.id = 1
    message = MagicMock()
    message.edit_text = AsyncMock()
    query.message = message
    query.answer = AsyncMock()

    state = AsyncMock()

    await goals.open_goals(query, state)

    update_limits_mock.assert_called_once_with(user)
    assert user.goal_trial_start is not None
    message.edit_text.assert_awaited_once_with(
        f"{GOAL_INTRO_TEXT}\n\n{GOAL_FREE_TRIAL_NOTE}",
        reply_markup="kb",
    )
    session.close.assert_called_once()
    assert session.commit.call_count >= 1
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_goals_shows_paywall_after_trial_expired(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    goal = Goal()
    goal.calories = 1500
    user = MagicMock()
    user.goal = goal
    user.grade = "free"
    user.goal_trial_start = datetime.utcnow() - timedelta(days=4)
    user.goal_trial_notified = False
    user.timezone = 0
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))

    update_limits_mock = MagicMock()
    monkeypatch.setattr(goals, "update_limits", update_limits_mock)

    monkeypatch.setattr(goals, "goal_trial_paywall_kb", MagicMock(return_value="paywall"))
    subscribe_button_mock = MagicMock(return_value="sub_kb")
    monkeypatch.setattr(goals, "subscribe_button", subscribe_button_mock)

    query = MagicMock()
    query.from_user.id = 1
    message = MagicMock()
    message.edit_text = AsyncMock()
    message.answer = AsyncMock()
    query.message = message
    query.answer = AsyncMock()

    state = AsyncMock()

    await goals.open_goals(query, state)

    update_limits_mock.assert_called_once_with(user)
    session.delete.assert_called_once_with(goal)
    message.answer.assert_awaited_once_with(
        GOAL_TRIAL_EXPIRED_NOTICE,
        reply_markup="sub_kb",
    )
    message.edit_text.assert_awaited_once_with(
        GOAL_TRIAL_PAYWALL_TEXT,
        reply_markup="paywall",
    )
    assert user.goal_trial_notified is True
    session.close.assert_called_once()
    assert session.commit.call_count >= 1
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_goal_reminder_settings_shows_local_time(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    user = MagicMock()
    user.goal = Goal()
    user.timezone = 60
    user.morning_time = "08:00"
    user.evening_time = "20:00"
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))
    monkeypatch.setattr(goals, "goal_reminders_settings_kb", MagicMock(return_value="kb"))

    message = MagicMock()
    message.edit_text = AsyncMock()

    query = MagicMock()
    query.from_user.id = 1
    query.message = message
    query.answer = AsyncMock()

    fake_now = datetime(2025, 1, 1, 12, 0)

    class DummyDatetime:
        @classmethod
        def utcnow(cls):
            return fake_now

    monkeypatch.setattr(goals, "datetime", DummyDatetime)

    await goals.goal_reminder_settings(query)

    message.edit_text.assert_awaited_once()
    text_arg = message.edit_text.call_args[0][0]
    assert "13:00" in text_arg
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_goal_set_morning_prompt(monkeypatch):
    message = MagicMock()
    message.message_id = 7
    message.edit_text = AsyncMock()
    message.edit_reply_markup = AsyncMock()

    query = MagicMock()
    query.message = message
    query.answer = AsyncMock()

    state = AsyncMock()

    await goals.goal_set_morning_prompt(query, state)

    message.edit_text.assert_awaited_once()
    state.update_data.assert_awaited_once_with(prompt_id=7)
    state.set_state.assert_awaited_once_with(goals.GoalReminderState.set_morning)
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_goal_process_morning_time(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))

    user = MagicMock()
    user.goal = Goal()
    user.timezone = 0
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))
    monkeypatch.setattr(goals, "goal_reminders_settings_kb", MagicMock(return_value="kb"))

    message = MagicMock()
    message.text = "09:30"
    message.chat.id = 1
    message.delete = AsyncMock()
    message.bot = MagicMock()
    message.bot.edit_message_text = AsyncMock()

    state = AsyncMock()
    state.get_data.return_value = {"prompt_id": 42}
    state.clear = AsyncMock()

    fake_now = datetime(2025, 1, 1, 12, 0)

    class DummyDatetime:
        @classmethod
        def utcnow(cls):
            return fake_now

    monkeypatch.setattr(goals, "datetime", DummyDatetime)

    await goals.goal_process_morning_time(message, state)

    assert user.morning_time == "09:30"
    message.bot.edit_message_text.assert_awaited_once()
    text_arg = message.bot.edit_message_text.call_args[0][0]
    assert "12:00" in text_arg
    session.commit.assert_called_once()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_goal_trial_expiry_disables_feature(monkeypatch):
    user = MagicMock()
    goal = Goal(
        target="loss",
        calories=1800,
        protein=120,
        fat=50,
        carbs=200,
        reminder_morning=True,
        reminder_evening=True,
    )
    user.goal = goal
    user.id = 1
    user.telegram_id = 123
    user.timezone = 0
    user.morning_time = "08:00"
    user.evening_time = "20:00"
    user.morning_enabled = False
    user.day_enabled = False
    user.evening_enabled = False
    user.grade = "free"
    user.goal_trial_start = datetime(2025, 1, 1, 8, 0)
    user.goal_trial_notified = False

    fake_now = datetime(2025, 1, 4, 8, 1)

    query_users = MagicMock()
    query_users.join.return_value.filter.return_value.all.return_value = [user]

    meal_query = MagicMock()
    meal_query.filter.return_value.order_by.return_value.first.return_value = MagicMock(
        timestamp=fake_now - timedelta(days=1)
    )

    session = MagicMock()

    def query_side_effect(model):
        if model.__name__ == "User":
            return query_users
        return meal_query

    session.query.side_effect = query_side_effect
    monkeypatch.setattr(reminders, "SessionLocal", MagicMock(return_value=session))

    send_mock = AsyncMock()
    monkeypatch.setattr(reminders, "_send", send_mock)
    monkeypatch.setattr(reminders, "subscribe_button", MagicMock(return_value="kb"))
    monkeypatch.setattr(reminders, "_chat_completion", AsyncMock())

    monkeypatch.setattr(
        reminders,
        "datetime",
        SimpleNamespace(utcnow=lambda: fake_now, combine=datetime.combine),
    )

    async def fake_sleep(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(reminders, "asyncio", SimpleNamespace(sleep=fake_sleep))

    bot = MagicMock()

    with pytest.raises(asyncio.CancelledError):
        await reminders.reminder_watcher(check_interval=0)(bot)

    session.delete.assert_called_once_with(goal)
    send_mock.assert_awaited_once_with(
        bot,
        user,
        GOAL_TRIAL_EXPIRED_NOTICE,
        reply_markup="kb",
    )
    assert user.goal_trial_notified is True


@pytest.mark.asyncio
async def test_goal_morning_notification_sent(monkeypatch):
    user = MagicMock()
    goal = Goal(target="loss", calories=2000, protein=100, fat=50, carbs=250, reminder_morning=True)
    user.goal = goal
    user.id = 1
    user.telegram_id = 123
    user.timezone = 0
    user.morning_time = "08:00"
    user.evening_time = None
    user.last_morning = None
    user.morning_enabled = False
    user.day_enabled = False
    user.evening_enabled = False

    fake_now = datetime(2025, 1, 1, 8, 0)

    query_users = MagicMock()
    query_users.join.return_value.filter.return_value.all.return_value = [user]

    last_meal_query = MagicMock()
    last_meal_query.filter.return_value.order_by.return_value.first.return_value = MagicMock(
        timestamp=fake_now - timedelta(days=1)
    )

    yday_meals_query = MagicMock()
    yday_meals_query.filter.return_value.all.return_value = []

    meal_queries = [last_meal_query, yday_meals_query]

    session = MagicMock()

    def query_side_effect(model):
        if model.__name__ == "User":
            return query_users
        return meal_queries.pop(0)

    session.query.side_effect = query_side_effect
    monkeypatch.setattr(reminders, "SessionLocal", MagicMock(return_value=session))

    monkeypatch.setattr(reminders, "_chat_completion", AsyncMock(return_value=("hi", 1, 1)))
    tm = SimpleNamespace(add=AsyncMock())
    monkeypatch.setattr(reminders, "token_monitor", tm)

    monkeypatch.setattr(
        reminders,
        "datetime",
        SimpleNamespace(utcnow=lambda: fake_now, combine=datetime.combine),
    )

    async def fake_sleep(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(reminders, "asyncio", SimpleNamespace(sleep=fake_sleep))

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with pytest.raises(asyncio.CancelledError):
        await reminders.reminder_watcher(check_interval=0)(bot)

    bot.send_message.assert_awaited_once_with(123, "hi", reply_markup=None)


@pytest.mark.asyncio
async def test_goal_evening_notification_sent(monkeypatch):
    user = MagicMock()
    goal = Goal(target="gain", calories=1800, protein=90, fat=60, carbs=210, reminder_evening=True)
    user.goal = goal
    user.id = 1
    user.telegram_id = 123
    user.timezone = 0
    user.morning_time = None
    user.evening_time = "20:00"
    user.last_evening = None
    user.morning_enabled = False
    user.day_enabled = False
    user.evening_enabled = False

    fake_now = datetime(2025, 1, 1, 20, 0)

    query_users = MagicMock()
    query_users.join.return_value.filter.return_value.all.return_value = [user]

    meal = MagicMock()
    meal.calories = 100
    meal.protein = 10
    meal.fat = 5
    meal.carbs = 20
    meal.name = "Салат"

    last_meal_query = MagicMock()
    last_meal_query.filter.return_value.order_by.return_value.first.return_value = MagicMock(
        timestamp=fake_now - timedelta(days=1)
    )

    day_meals_query = MagicMock()
    day_meals_query.filter.return_value.all.return_value = [meal]

    meal_queries = [last_meal_query, day_meals_query]

    session = MagicMock()

    def query_side_effect(model):
        if model.__name__ == "User":
            return query_users
        return meal_queries.pop(0)

    session.query.side_effect = query_side_effect
    monkeypatch.setattr(reminders, "SessionLocal", MagicMock(return_value=session))

    monkeypatch.setattr(reminders, "_chat_completion", AsyncMock(return_value=("ok", 1, 1)))
    tm = SimpleNamespace(add=AsyncMock())
    monkeypatch.setattr(reminders, "token_monitor", tm)

    monkeypatch.setattr(
        reminders,
        "datetime",
        SimpleNamespace(utcnow=lambda: fake_now, combine=datetime.combine),
    )

    async def fake_sleep(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(reminders, "asyncio", SimpleNamespace(sleep=fake_sleep))

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with pytest.raises(asyncio.CancelledError):
        await reminders.reminder_watcher(check_interval=0)(bot)

    bot.send_message.assert_awaited_once_with(123, "ok", reply_markup=None)


@pytest.mark.asyncio
async def test_goal_auto_stop_after_inactivity(monkeypatch):
    user = MagicMock()
    goal = Goal(
        target="maintain",
        calories=2000,
        protein=100,
        fat=50,
        carbs=250,
        reminder_morning=True,
        reminder_evening=True,
    )
    user.goal = goal
    user.id = 1
    user.telegram_id = 123
    user.timezone = 0
    user.morning_time = "08:00"
    user.evening_time = "20:00"
    user.morning_enabled = False
    user.day_enabled = False
    user.evening_enabled = False
    user.grade = "light"

    fake_now = datetime(2025, 1, 4, 8, 0)

    query_users = MagicMock()
    query_users.join.return_value.filter.return_value.all.return_value = [user]

    last_meal_query = MagicMock()
    last_meal_query.filter.return_value.order_by.return_value.first.return_value = MagicMock(
        timestamp=fake_now - timedelta(days=4)
    )

    session = MagicMock()

    def query_side_effect(model):
        if model.__name__ == "User":
            return query_users
        return last_meal_query

    session.query.side_effect = query_side_effect
    monkeypatch.setattr(reminders, "SessionLocal", MagicMock(return_value=session))

    monkeypatch.setattr(
        reminders,
        "datetime",
        SimpleNamespace(utcnow=lambda: fake_now, combine=datetime.combine),
    )

    send_mock = AsyncMock()
    monkeypatch.setattr(reminders, "_send", send_mock)
    monkeypatch.setattr(reminders, "_chat_completion", AsyncMock())
    tm = SimpleNamespace(add=AsyncMock())
    monkeypatch.setattr(reminders, "token_monitor", tm)

    async def fake_sleep(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(reminders, "asyncio", SimpleNamespace(sleep=fake_sleep))

    bot = MagicMock()

    with pytest.raises(asyncio.CancelledError):
        await reminders.reminder_watcher(check_interval=0)(bot)

    session.delete.assert_called_once_with(goal)
    send_mock.assert_awaited_once_with(bot, user, GOAL_REMINDERS_DISABLED, reply_markup=None)


@pytest.mark.asyncio
async def test_goal_auto_stop_after_inactivity_free_no_notice(monkeypatch):
    user = MagicMock()
    goal = Goal(
        target="maintain",
        calories=2000,
        protein=100,
        fat=50,
        carbs=250,
        reminder_morning=True,
        reminder_evening=True,
    )
    user.goal = goal
    user.id = 1
    user.telegram_id = 123
    user.timezone = 0
    user.morning_time = "08:00"
    user.evening_time = "20:00"
    user.morning_enabled = False
    user.day_enabled = False
    user.evening_enabled = False
    user.grade = "free"

    fake_now = datetime(2025, 1, 4, 8, 0)

    query_users = MagicMock()
    query_users.join.return_value.filter.return_value.all.return_value = [user]

    last_meal_query = MagicMock()
    last_meal_query.filter.return_value.order_by.return_value.first.return_value = MagicMock(
        timestamp=fake_now - timedelta(days=4)
    )

    session = MagicMock()

    def query_side_effect(model):
        if model.__name__ == "User":
            return query_users
        return last_meal_query

    session.query.side_effect = query_side_effect
    monkeypatch.setattr(reminders, "SessionLocal", MagicMock(return_value=session))

    monkeypatch.setattr(
        reminders,
        "datetime",
        SimpleNamespace(utcnow=lambda: fake_now, combine=datetime.combine),
    )

    send_mock = AsyncMock()
    monkeypatch.setattr(reminders, "_send", send_mock)
    monkeypatch.setattr(reminders, "_chat_completion", AsyncMock())
    tm = SimpleNamespace(add=AsyncMock())
    monkeypatch.setattr(reminders, "token_monitor", tm)

    async def fake_sleep(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(reminders, "asyncio", SimpleNamespace(sleep=fake_sleep))

    bot = MagicMock()

    with pytest.raises(asyncio.CancelledError):
        await reminders.reminder_watcher(check_interval=0)(bot)

    session.delete.assert_called_once_with(goal)
    send_mock.assert_not_awaited()

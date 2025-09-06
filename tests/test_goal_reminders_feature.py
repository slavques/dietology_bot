import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.handlers import goals  # noqa: E402
from bot.database import Goal  # noqa: E402


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

    monkeypatch.setattr(goals, "goal_reminders_kb", MagicMock(return_value="kb"))

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

    monkeypatch.setattr(goals, "goal_reminders_kb", MagicMock(return_value="kb"))

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
    session.commit.assert_called_once()
    session.close.assert_called_once()


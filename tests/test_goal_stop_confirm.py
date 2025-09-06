import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.handlers import goals  # noqa: E402
from bot.keyboards import main_menu_kb  # noqa: E402
from bot.texts import GOAL_STOP_DONE  # noqa: E402


@pytest.mark.asyncio
async def test_goal_stop_confirm_sends_main_menu_keyboard(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(goals, "SessionLocal", MagicMock(return_value=session))
    user = MagicMock()
    user.goal = object()
    monkeypatch.setattr(goals, "ensure_user", MagicMock(return_value=user))

    message = MagicMock()
    message.delete = AsyncMock()
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()

    query = MagicMock()
    query.from_user.id = 1
    query.message = message
    query.answer = AsyncMock()

    await goals.goal_stop_confirm(query)

    message.delete.assert_awaited_once()
    message.answer.assert_awaited_once_with(GOAL_STOP_DONE, reply_markup=main_menu_kb())
    message.edit_text.assert_not_called()
    session.delete.assert_called_once_with(user.goal)
    session.commit.assert_called_once()
    session.close.assert_called_once()
    query.answer.assert_awaited_once()

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ensure database URL for handlers import
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.handlers.goals import process_age, process_weight, GoalState  # noqa: E402
from bot.keyboards import goal_back_kb, goal_body_fat_kb  # noqa: E402
from bot.texts import GOAL_ENTER_HEIGHT, GOAL_CHOOSE_BODY_FAT  # noqa: E402


@pytest.mark.asyncio
async def test_process_age_edits_prompt_and_deletes_input():
    message = MagicMock()
    message.text = "25"
    message.chat.id = 1
    message.delete = AsyncMock()
    message.answer = AsyncMock()
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    message.bot = bot

    state = AsyncMock()
    state.get_data.return_value = {"msg_id": 42}

    await process_age(message, state)

    message.delete.assert_awaited_once()
    bot.edit_message_text.assert_awaited_once_with(
        GOAL_ENTER_HEIGHT,
        chat_id=1,
        message_id=42,
        reply_markup=goal_back_kb("age"),
    )
    message.answer.assert_not_called()
    state.set_state.assert_awaited_once_with(GoalState.height)


@pytest.mark.asyncio
async def test_process_weight_moves_to_activity_and_deletes_input():
    message = MagicMock()
    message.text = "70"
    message.chat.id = 1
    message.delete = AsyncMock()
    message.answer = AsyncMock()
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    message.bot = bot

    state = AsyncMock()
    state.get_data.return_value = {"msg_id": 99}

    await process_weight(message, state)

    message.delete.assert_awaited_once()
    bot.edit_message_text.assert_awaited_once_with(
        GOAL_CHOOSE_BODY_FAT,
        chat_id=1,
        message_id=99,
        reply_markup=goal_body_fat_kb(),
    )
    message.answer.assert_not_called()
    state.set_state.assert_awaited_once_with(GoalState.body_fat)

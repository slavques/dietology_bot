import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.keyboards import goal_start_kb  # noqa: E402
from bot.texts import BTN_GOAL_START, BTN_BACK  # noqa: E402


def test_goal_start_keyboard_structure():
    kb = goal_start_kb()
    inline_keyboard = kb.inline_keyboard
    assert len(inline_keyboard) == 2
    assert inline_keyboard[0][0].text == BTN_GOAL_START
    assert inline_keyboard[0][0].callback_data == "goal_start"
    assert inline_keyboard[1][0].text == BTN_BACK
    assert inline_keyboard[1][0].callback_data == "stats_menu"

import os, sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot import keyboards, texts  # noqa: E402


def test_menu_contains_bonus_button():
    kb = keyboards.menu_inline_kb()
    buttons = [btn.text for row in kb.inline_keyboard for btn in row]
    assert texts.BTN_BONUSES in buttons

import os, sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot import keyboards, texts  # noqa: E402
from bot.database import set_option


def test_tariffs_menu_contains_bonus_button():
    kb = keyboards.tariffs_menu_inline_kb()
    buttons = [btn.text for row in kb.inline_keyboard for btn in row]
    assert texts.BTN_BONUSES in buttons


def test_tariffs_menu_hides_bonus_button_when_disabled():
    set_option("feat_referral", "0")
    kb = keyboards.tariffs_menu_inline_kb()
    buttons = [btn.text for row in kb.inline_keyboard for btn in row]
    assert texts.BTN_BONUSES not in buttons

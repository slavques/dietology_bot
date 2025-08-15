import os
import sys
from pathlib import Path
from datetime import datetime
import os
import sys
from pathlib import Path
from datetime import datetime
import asyncio
from unittest.mock import AsyncMock

import pytest
from aiogram import types

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import Base, engine, SessionLocal, set_option, User  # noqa: E402
from bot.subscriptions import ensure_user  # noqa: E402
from bot.handlers.start import cmd_start  # noqa: E402


class DummyReply:
    async def edit_text(self, *args, **kwargs):
        pass


class DummyMessage:
    def __init__(self, text: str, user_id: int):
        self.text = text
        self.from_user = types.User(id=user_id, is_bot=False, first_name="T")
        self.bot = AsyncMock()

    async def answer(self, *args, **kwargs):
        return DummyReply()


def _setup_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    set_option("feat_referral", "1")
    set_option("trial_light_enabled", "0")
    set_option("trial_pro_enabled", "0")


def test_new_user_receives_referral(monkeypatch):
    _setup_db()
    session = SessionLocal()
    ensure_user(session, 10)
    session.close()

    monkeypatch.setattr("bot.handlers.start.notify_trial_end", AsyncMock())
    monkeypatch.setattr("bot.alerts.new_user", AsyncMock())

    msg = DummyMessage("/start ref_10", 20)
    asyncio.run(cmd_start(msg))

    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=20).one()
    assert user.referrer_id == 10
    assert user.trial is True
    assert user.trial_end is not None
    assert (user.trial_end - datetime.utcnow()).days >= 4
    session.close()


def test_self_referral_does_nothing(monkeypatch):
    _setup_db()

    monkeypatch.setattr("bot.handlers.start.notify_trial_end", AsyncMock())
    monkeypatch.setattr("bot.alerts.new_user", AsyncMock())

    msg = DummyMessage("/start ref_5", 5)
    asyncio.run(cmd_start(msg))

    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=5).one()
    assert user.referrer_id is None
    assert user.trial is False
    assert user.trial_end is None
    session.close()


def test_existing_user_referral_ignored(monkeypatch):
    _setup_db()
    session = SessionLocal()
    ensure_user(session, 30)
    session.close()

    monkeypatch.setattr("bot.handlers.start.notify_trial_end", AsyncMock())
    monkeypatch.setattr("bot.alerts.new_user", AsyncMock())

    msg = DummyMessage("/start ref_40", 30)
    asyncio.run(cmd_start(msg))

    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=30).one()
    assert user.referrer_id is None
    assert user.trial is False
    assert user.trial_end is None
    session.close()

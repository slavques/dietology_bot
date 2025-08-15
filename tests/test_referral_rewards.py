import os
import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import Base, engine, SessionLocal, set_option  # noqa: E402
from bot.subscriptions import ensure_user  # noqa: E402
from bot.handlers.referral import (  # noqa: E402
    reward_first_analysis,
    reward_subscription,
)
from bot.texts import (  # noqa: E402
    REFERRAL_FRIEND_ACTIVATED,
    REFERRAL_FRIEND_PAID,
)


def _setup_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    set_option("feat_referral", "1")


def test_reward_first_analysis_gives_days_and_notifies():
    _setup_db()
    session = SessionLocal()
    referrer = ensure_user(session, 1)
    invitee = ensure_user(session, 2)
    invitee.referrer_id = referrer.telegram_id
    invitee.requests_total = 1
    session.commit()

    bot = AsyncMock()
    asyncio.run(reward_first_analysis(bot, session, invitee))
    session.refresh(referrer)

    bot.send_message.assert_awaited_with(
        referrer.telegram_id, REFERRAL_FRIEND_ACTIVATED
    )
    assert referrer.trial is True
    assert referrer.trial_end - datetime.utcnow() > timedelta(days=4)
    session.close()


def test_reward_subscription_gives_days_and_notifies():
    _setup_db()
    session = SessionLocal()
    referrer = ensure_user(session, 10)
    invitee = ensure_user(session, 20)
    invitee.referrer_id = referrer.telegram_id
    session.commit()

    bot = AsyncMock()
    asyncio.run(reward_subscription(bot, session, invitee, payments=1))
    session.refresh(referrer)

    bot.send_message.assert_awaited_with(
        referrer.telegram_id, REFERRAL_FRIEND_PAID
    )
    assert referrer.trial is True
    assert referrer.trial_end - datetime.utcnow() > timedelta(days=29)
    session.close()


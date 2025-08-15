import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import Base, engine, SessionLocal, Payment  # noqa: E402
from bot.subscriptions import ensure_user  # noqa: E402
from bot.handlers.referral import get_referral_stats  # noqa: E402



def _setup_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_referral_stats_count_and_days():
    _setup_db()
    session = SessionLocal()
    referrer = ensure_user(session, 100)
    # friend who only joined
    f1 = ensure_user(session, 101)
    f1.referrer_id = referrer.telegram_id
    # friend who made first request
    f2 = ensure_user(session, 102)
    f2.referrer_id = referrer.telegram_id
    f2.requests_total = 1
    # friend who made request and paid
    f3 = ensure_user(session, 103)
    f3.referrer_id = referrer.telegram_id
    f3.requests_total = 1
    session.add(Payment(user_id=f3.id, tier="light", months=1))
    session.commit()

    count, days = get_referral_stats(session, referrer.telegram_id)
    assert count == 3
    assert days == 40
    session.close()

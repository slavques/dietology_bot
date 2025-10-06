import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.discounts import determine_discount_type  # noqa: E402
from bot.database import EngagementStatus, Payment, Subscription, User  # noqa: E402


class DummyQuery:
    def __init__(self, payments):
        self._payments = payments

    def filter_by(self, **kwargs):  # noqa: D401 - matching SQLAlchemy API
        return self

    def order_by(self, *args, **kwargs):  # noqa: D401 - matching SQLAlchemy API
        return self

    def all(self):
        return self._payments


class DummySession:
    def __init__(self, payments=None):
        self._payments = payments or []

    def query(self, model):  # noqa: D401 - matching SQLAlchemy API
        return DummyQuery(self._payments)


@pytest.fixture
def decision_time():
    return datetime.utcnow()


def _base_user(decision_time):
    user = User()
    user.id = 1
    user.telegram_id = 1001
    user.created_at = decision_time - timedelta(days=10)
    user.blocked = False
    user.left_bot = False
    return user


def _subscription(*, grade="free", trial=False, trial_end=None):
    subscription = Subscription()
    subscription.grade = grade
    subscription.trial = trial
    subscription.trial_end = trial_end
    return subscription


def _payment(decision_time, *, days_ago, months=1):
    payment = Payment()
    payment.user_id = 1
    payment.months = months
    payment.timestamp = decision_time - timedelta(days=days_ago)
    return payment


def test_determine_discount_type_skips_active_trial(decision_time):
    user = _base_user(decision_time)
    subscription = Subscription()
    subscription.grade = "free"
    subscription.trial = True
    subscription.trial_end = decision_time + timedelta(days=2)
    user.subscription = subscription

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "Active trial must not receive a discount"


def test_determine_discount_type_allows_after_trial_end(decision_time):
    user = _base_user(decision_time)
    subscription = Subscription()
    subscription.grade = "light_promo"
    subscription.trial = True
    subscription.trial_end = decision_time - timedelta(days=1)
    user.subscription = subscription

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) == "new"
    ), "Expired trial should be treated as eligible for discount"


def test_determine_discount_type_requires_subscription(decision_time):
    user = _base_user(decision_time)
    user.subscription = None

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "Users without subscriptions must be skipped"


def test_determine_discount_type_blocks_future_trial_end_even_without_flag(
    decision_time,
):
    user = _base_user(decision_time)
    user.subscription = _subscription(trial=False, trial_end=decision_time + timedelta(days=1))

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "Future trial end should block discounts even if trial flag already cleared"


def test_determine_discount_type_blocks_paid_grade_before_trial_ends(decision_time):
    user = _base_user(decision_time)
    user.subscription = _subscription(grade="premium", trial=False)

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "Active paying users should not receive discounts"


def test_determine_discount_type_skips_blocked_user(decision_time):
    user = _base_user(decision_time)
    user.blocked = True
    user.subscription = _subscription()

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "Blocked users must be skipped by default"


def test_determine_discount_type_allows_inactive_when_skip_disabled(decision_time):
    user = _base_user(decision_time)
    user.blocked = True
    user.subscription = _subscription()

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time, skip_inactive=False) == "new"
    ), "Inactive users can be targeted when skip_inactive is False"


def test_determine_discount_type_respects_cooldown(decision_time):
    user = _base_user(decision_time)
    user.subscription = _subscription()
    engagement = EngagementStatus()
    engagement.discount_last_sent = decision_time - timedelta(days=5)
    engagement.discount_sent = True
    user.engagement = engagement

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "Users within the cooldown window must not receive a new discount"


def test_determine_discount_type_ignores_cooldown_when_disabled(decision_time):
    user = _base_user(decision_time)
    user.subscription = _subscription()
    engagement = EngagementStatus()
    engagement.discount_last_sent = decision_time - timedelta(days=5)
    engagement.discount_sent = True
    user.engagement = engagement

    session = DummySession()

    assert (
        determine_discount_type(
            session, user, decision_time, respect_cooldown=False
        )
        == "new"
    ), "Disabling cooldown should allow discount to be sent"


def test_determine_discount_type_requires_minimum_account_age(decision_time):
    user = _base_user(decision_time)
    user.created_at = decision_time - timedelta(days=1)
    user.subscription = _subscription()

    session = DummySession()

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "New users should not receive discounts immediately"


def test_determine_discount_type_returns_for_lapsed_payments(decision_time):
    user = _base_user(decision_time)
    user.subscription = _subscription()

    payments = [
        _payment(decision_time, days_ago=70),
    ]

    session = DummySession(payments)

    assert (
        determine_discount_type(session, user, decision_time) == "return"
    ), "Users whose payments lapsed more than three days ago should receive a return discount"


def test_determine_discount_type_skips_recent_payments(decision_time):
    user = _base_user(decision_time)
    user.subscription = _subscription()

    payments = [
        _payment(decision_time, days_ago=10),
    ]

    session = DummySession(payments)

    assert (
        determine_discount_type(session, user, decision_time) is None
    ), "Users with active paid time remaining must not receive discounts"

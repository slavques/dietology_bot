import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot import subscriptions  # noqa: E402


class DummyUser:
    def __init__(self):
        self.id = 1
        self.telegram_id = 123456789
        self.trial = False
        self.trial_end = None
        self.resume_grade = None
        self.resume_period_end = None
        self.grade = "free"
        self.period_end = None
        self.request_limit = 0
        self.requests_used = 0
        self.notified_7d = False
        self.notified_3d = False
        self.notified_1d = False
        self.notified_0d = False
        self.goal_trial_start = None
        self.goal_trial_notified = False
        self.trial_used = False


def test_process_payment_marks_trial_used():
    user = DummyUser()
    session = MagicMock()

    subscriptions.process_payment_success(session, user, months=1, grade="light")

    assert user.trial_used is True

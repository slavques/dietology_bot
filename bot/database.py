from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    text,  # for raw SQL migrations
    inspect,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from typing import Optional

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def _column_names(table: str) -> set[str]:
    """Return existing column names for given table."""
    inspector = inspect(engine)
    try:
        cols = inspector.get_columns(table)
    except Exception:
        return set()
    return {c["name"] for c in cols}


def _ensure_columns():
    """Add new columns to old databases if they are missing."""
    existing = _column_names("users")
    bool_default = "0" if engine.dialect.name == "sqlite" else "FALSE"
    with engine.begin() as conn:
        if "blocked" not in existing:
            conn.execute(
                text(
                    f"ALTER TABLE users ADD COLUMN blocked BOOLEAN DEFAULT {bool_default}"
                )
            )
        if "left_bot" not in existing:
            conn.execute(
                text(
                    f"ALTER TABLE users ADD COLUMN left_bot BOOLEAN DEFAULT {bool_default}"
                )
            )
        if "referrer_id" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN referrer_id BIGINT"))

    existing = _column_names("meals")
    with engine.begin() as conn:
        if "type" not in existing:
            conn.execute(text("ALTER TABLE meals ADD COLUMN type TEXT DEFAULT 'meal'"))

    existing = _column_names("subscriptions")
    with engine.begin() as conn:
        if "last_request" not in existing:
            conn.execute(text("ALTER TABLE subscriptions ADD COLUMN last_request TIMESTAMP"))
        if "goal_trial_start" not in existing:
            conn.execute(text("ALTER TABLE subscriptions ADD COLUMN goal_trial_start TIMESTAMP"))
        if "goal_trial_notified" not in existing:
            conn.execute(
                text(
                    f"ALTER TABLE subscriptions ADD COLUMN goal_trial_notified BOOLEAN DEFAULT {bool_default}"
                )
            )

    existing = _column_names("engagement_status")
    with engine.begin() as conn:
        if "discount_sent" not in existing:
            conn.execute(
                text(
                    f"ALTER TABLE engagement_status ADD COLUMN discount_sent BOOLEAN DEFAULT {bool_default}"
                )
            )
        if "discount_expires" not in existing:
            conn.execute(text("ALTER TABLE engagement_status ADD COLUMN discount_expires TIMESTAMP"))
        if "discount_last_sent" not in existing:
            conn.execute(
                text("ALTER TABLE engagement_status ADD COLUMN discount_last_sent TIMESTAMP")
            )

    existing = _column_names("goals")
    with engine.begin() as conn:
        if "body_fat" not in existing:
            conn.execute(text("ALTER TABLE goals ADD COLUMN body_fat FLOAT"))
        if "plan" not in existing:
            conn.execute(text("ALTER TABLE goals ADD COLUMN plan TEXT"))
        if "reactivated_at" not in existing:
            conn.execute(text("ALTER TABLE goals ADD COLUMN reactivated_at TIMESTAMP"))


def _drop_request_logs():
    """Remove legacy request_logs table if it still exists."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS request_logs"))


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    blocked = Column(Boolean, default=False)
    left_bot = Column(Boolean, default=False)
    referrer_id = Column(BigInteger, nullable=True)

    subscription = relationship(
        'Subscription',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    notification = relationship(
        'NotificationStatus',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    reminders = relationship(
        'ReminderSettings',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    engagement = relationship(
        'EngagementStatus',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    meals = relationship(
        'Meal',
        back_populates='user',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    goal = relationship(
        'Goal',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    # convenience proxies for old attribute names
    def _sub(self):
        if not self.subscription:
            self.subscription = Subscription()
        return self.subscription

    def _notif(self):
        if not self.notification:
            self.notification = NotificationStatus()
        return self.notification

    def _rem(self):
        if not self.reminders:
            self.reminders = ReminderSettings()
        return self.reminders

    def _eng(self):
        if not self.engagement:
            self.engagement = EngagementStatus()
        return self.engagement

    grade = property(lambda self: self._sub().grade, lambda self, v: setattr(self._sub(), 'grade', v))
    request_limit = property(lambda self: self._sub().request_limit, lambda self, v: setattr(self._sub(), 'request_limit', v))
    requests_used = property(lambda self: self._sub().requests_used, lambda self, v: setattr(self._sub(), 'requests_used', v))
    requests_total = property(lambda self: self._sub().requests_total, lambda self, v: setattr(self._sub(), 'requests_total', v))
    monthly_used = property(lambda self: self._sub().monthly_used, lambda self, v: setattr(self._sub(), 'monthly_used', v))
    monthly_start = property(lambda self: self._sub().monthly_start, lambda self, v: setattr(self._sub(), 'monthly_start', v))
    period_start = property(lambda self: self._sub().period_start, lambda self, v: setattr(self._sub(), 'period_start', v))
    period_end = property(lambda self: self._sub().period_end, lambda self, v: setattr(self._sub(), 'period_end', v))
    trial_end = property(lambda self: self._sub().trial_end, lambda self, v: setattr(self._sub(), 'trial_end', v))
    resume_grade = property(lambda self: self._sub().resume_grade, lambda self, v: setattr(self._sub(), 'resume_grade', v))
    resume_period_end = property(lambda self: self._sub().resume_period_end, lambda self, v: setattr(self._sub(), 'resume_period_end', v))
    daily_used = property(lambda self: self._sub().daily_used, lambda self, v: setattr(self._sub(), 'daily_used', v))
    daily_start = property(lambda self: self._sub().daily_start, lambda self, v: setattr(self._sub(), 'daily_start', v))
    last_request = property(lambda self: self._sub().last_request, lambda self, v: setattr(self._sub(), 'last_request', v))
    trial = property(lambda self: self._sub().trial, lambda self, v: setattr(self._sub(), 'trial', v))
    trial_used = property(lambda self: self._sub().trial_used, lambda self, v: setattr(self._sub(), 'trial_used', v))
    goal_trial_start = property(
        lambda self: self._sub().goal_trial_start,
        lambda self, v: setattr(self._sub(), 'goal_trial_start', v),
    )
    goal_trial_notified = property(
        lambda self: self._sub().goal_trial_notified,
        lambda self, v: setattr(self._sub(), 'goal_trial_notified', v),
    )

    notified_7d = property(lambda self: self._notif().notified_7d, lambda self, v: setattr(self._notif(), 'notified_7d', v))
    notified_3d = property(lambda self: self._notif().notified_3d, lambda self, v: setattr(self._notif(), 'notified_3d', v))
    notified_1d = property(lambda self: self._notif().notified_1d, lambda self, v: setattr(self._notif(), 'notified_1d', v))
    notified_0d = property(lambda self: self._notif().notified_0d, lambda self, v: setattr(self._notif(), 'notified_0d', v))
    notified_free = property(lambda self: self._notif().notified_free, lambda self, v: setattr(self._notif(), 'notified_free', v))

    timezone = property(lambda self: self._rem().timezone, lambda self, v: setattr(self._rem(), 'timezone', v))
    morning_time = property(lambda self: self._rem().morning_time, lambda self, v: setattr(self._rem(), 'morning_time', v))
    day_time = property(lambda self: self._rem().day_time, lambda self, v: setattr(self._rem(), 'day_time', v))
    evening_time = property(lambda self: self._rem().evening_time, lambda self, v: setattr(self._rem(), 'evening_time', v))
    morning_enabled = property(lambda self: self._rem().morning_enabled, lambda self, v: setattr(self._rem(), 'morning_enabled', v))
    day_enabled = property(lambda self: self._rem().day_enabled, lambda self, v: setattr(self._rem(), 'day_enabled', v))
    evening_enabled = property(lambda self: self._rem().evening_enabled, lambda self, v: setattr(self._rem(), 'evening_enabled', v))
    last_morning = property(lambda self: self._rem().last_morning, lambda self, v: setattr(self._rem(), 'last_morning', v))
    last_day = property(lambda self: self._rem().last_day, lambda self, v: setattr(self._rem(), 'last_day', v))
    last_evening = property(lambda self: self._rem().last_evening, lambda self, v: setattr(self._rem(), 'last_evening', v))

class Subscription(Base):
    __tablename__ = 'subscriptions'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    grade = Column(String, default='free')
    request_limit = Column(Integer, default=20)
    requests_used = Column(Integer, default=0)
    requests_total = Column(Integer, default=0)
    monthly_used = Column(Integer, default=0)
    monthly_start = Column(DateTime, default=datetime.utcnow)
    period_start = Column(DateTime, default=datetime.utcnow)
    period_end = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    resume_grade = Column(String, nullable=True)
    resume_period_end = Column(DateTime, nullable=True)
    daily_used = Column(Integer, default=0)
    daily_start = Column(DateTime, default=datetime.utcnow)
    last_request = Column(DateTime, nullable=True)
    trial = Column(Boolean, default=False)
    trial_used = Column(Boolean, default=False)
    goal_trial_start = Column(DateTime, nullable=True)
    goal_trial_notified = Column(Boolean, default=False)

    user = relationship('User', back_populates='subscription')


class NotificationStatus(Base):
    __tablename__ = 'notification_status'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    notified_7d = Column(Boolean, default=False)
    notified_3d = Column(Boolean, default=False)
    notified_1d = Column(Boolean, default=False)
    notified_0d = Column(Boolean, default=False)
    notified_free = Column(Boolean, default=False)

    user = relationship('User', back_populates='notification')


class EngagementStatus(Base):
    __tablename__ = 'engagement_status'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    no_request_15m = Column(Boolean, default=False)
    no_request_24h = Column(Boolean, default=False)
    no_request_3d = Column(Boolean, default=False)
    first_request_sent = Column(Boolean, default=False)
    three_requests_sent = Column(Boolean, default=False)
    seven_requests_sent = Column(Boolean, default=False)
    feedback_10d_sent = Column(Boolean, default=False)
    five_no_meal_sent = Column(Boolean, default=False)
    limit_reached_at = Column(DateTime, nullable=True)
    limit_reminder_sent = Column(Boolean, default=False)
    inactivity_7d_sent = Column(Boolean, default=False)
    inactivity_14d_sent = Column(Boolean, default=False)
    inactivity_30d_sent = Column(Boolean, default=False)
    discount_sent = Column(Boolean, default=False)
    discount_expires = Column(DateTime, nullable=True)
    discount_last_sent = Column(DateTime, nullable=True)

    user = relationship('User', back_populates='engagement')


class ReminderSettings(Base):
    __tablename__ = 'reminders'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    timezone = Column(Integer, nullable=True)
    morning_time = Column(String, default='08:00')
    day_time = Column(String, default='13:00')
    evening_time = Column(String, default='20:00')
    morning_enabled = Column(Boolean, default=False)
    day_enabled = Column(Boolean, default=False)
    evening_enabled = Column(Boolean, default=False)
    last_morning = Column(DateTime, nullable=True)
    last_day = Column(DateTime, nullable=True)
    last_evening = Column(DateTime, nullable=True)

    user = relationship('User', back_populates='reminders')


class Goal(Base):
    __tablename__ = 'goals'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    gender = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    body_fat = Column(Float, nullable=True)
    activity = Column(String, nullable=True)
    target = Column(String, nullable=True)
    plan = Column(String, nullable=True)
    calories = Column(Integer, nullable=True)
    protein = Column(Integer, nullable=True)
    fat = Column(Integer, nullable=True)
    carbs = Column(Integer, nullable=True)
    reminder_morning = Column(Boolean, default=False)
    reminder_evening = Column(Boolean, default=False)
    reactivated_at = Column(DateTime, nullable=True, default=datetime.utcnow)

    user = relationship('User', back_populates='goal')


class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    name = Column(String)
    ingredients = Column(String)
    type = Column(String, default='meal')
    serving = Column(Float)
    calories = Column(Float)
    protein = Column(Float)
    fat = Column(Float)
    carbs = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship('User', back_populates='meals')


class Payment(Base):
    """Record of a successful subscription purchase."""

    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    tier = Column(String)
    months = Column(Integer, default=1)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship('User')


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    text = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship('User')


class Option(Base):
    __tablename__ = 'options'

    key = Column(String, primary_key=True)
    value = Column(String)


def get_option(key: str, default: Optional[str] = None) -> Optional[str]:
    session = SessionLocal()
    row = session.query(Option).filter_by(key=key).first()
    result = row.value if row else default
    session.close()
    return result


def get_option_bool(key: str, default: bool = True) -> bool:
    val = get_option(key, "1" if default else "0")
    return str(val) == "1"


def get_option_int(key: str, default: int = 0) -> int:
    val = get_option(key)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


def set_option(key: str, value: str) -> None:
    session = SessionLocal()
    row = session.query(Option).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        row = Option(key=key, value=value)
        session.add(row)
    session.commit()
    session.close()


def _ensure_options():
    defaults = {
        "pay_card": "1",
        "pay_stars": "1",
        "pay_crypto": "1",
        "grade_light": "1",
        "grade_pro": "1",
        "feat_manual": "1",
        "feat_settings": "1",
        "feat_reminders": "1",
        "feat_goals": "1",
        "feat_referral": "1",
        "trial_pro_enabled": "0",
        "trial_pro_days": "0",
        "trial_light_enabled": "0",
        "trial_light_days": "0",
    }
    session = SessionLocal()
    for k, v in defaults.items():
        if not session.query(Option).filter_by(key=k).first():
            session.add(Option(key=k, value=v))
    session.commit()
    session.close()


def _ensure_cascades():
    """Ensure user_id foreign keys cascade on delete for existing tables."""
    if engine.dialect.name != "postgresql":
        return

    fks = {
        "subscriptions": "subscriptions_user_id_fkey",
        "notification_status": "notification_status_user_id_fkey",
        "reminders": "reminders_user_id_fkey",
        "goals": "goals_user_id_fkey",
        "engagement_status": "engagement_status_user_id_fkey",
        "meals": "meals_user_id_fkey",
        "payments": "payments_user_id_fkey",
        "comments": "comments_user_id_fkey",
    }

    with engine.begin() as conn:
        for table, fk in fks.items():
            conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fk}"))
            conn.execute(
                text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {fk} FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
                )
            )

Base.metadata.create_all(engine)
_ensure_columns()
_drop_request_logs()
_ensure_options()
_ensure_cascades()

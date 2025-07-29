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
    dt_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP"
    bool_default = "0" if engine.dialect.name == "sqlite" else "FALSE"
    with engine.begin() as conn:
        if "grade" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN grade TEXT DEFAULT 'free'"))
        else:
            conn.execute(text("UPDATE users SET grade='light' WHERE grade='paid'"))
        if "request_limit" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN request_limit INTEGER DEFAULT 20"))
        if "requests_used" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN requests_used INTEGER DEFAULT 0"))
        if "requests_total" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN requests_total INTEGER DEFAULT 0"))
        if "monthly_used" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN monthly_used INTEGER DEFAULT 0"))
        if "monthly_start" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN monthly_start {dt_type} DEFAULT CURRENT_TIMESTAMP"))
        if "period_start" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN period_start {dt_type} DEFAULT CURRENT_TIMESTAMP"))
        conn.execute(text("UPDATE users SET period_start=CURRENT_TIMESTAMP WHERE period_start IS NULL"))
        if "period_end" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN period_end {dt_type}"))
        if "notified_7d" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN notified_7d BOOLEAN DEFAULT {bool_default}"))
        if "notified_3d" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN notified_3d BOOLEAN DEFAULT {bool_default}"))
        if "notified_0d" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN notified_0d BOOLEAN DEFAULT {bool_default}"))
        if "notified_1d" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN notified_1d BOOLEAN DEFAULT {bool_default}"))
        if "notified_free" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN notified_free BOOLEAN DEFAULT {bool_default}"))
        if "daily_used" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN daily_used INTEGER DEFAULT 0"))
        if "daily_start" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN daily_start {dt_type} DEFAULT CURRENT_TIMESTAMP"))
        if "blocked" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN blocked BOOLEAN DEFAULT {bool_default}"))
        if "trial" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN trial BOOLEAN DEFAULT {bool_default}"))
        if "trial_used" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN trial_used BOOLEAN DEFAULT {bool_default}"))
        if "trial_end" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN trial_end {dt_type}"))
        if "resume_grade" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN resume_grade TEXT"))
        if "resume_period_end" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN resume_period_end {dt_type}"))
        if "timezone" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN timezone INTEGER"))
        if "morning_time" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN morning_time TEXT DEFAULT '08:00'"))
        if "day_time" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN day_time TEXT DEFAULT '13:00'"))
        if "evening_time" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN evening_time TEXT DEFAULT '20:00'"))
        if "morning_enabled" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN morning_enabled BOOLEAN DEFAULT {bool_default}"))
        if "day_enabled" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN day_enabled BOOLEAN DEFAULT {bool_default}"))
        if "evening_enabled" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN evening_enabled BOOLEAN DEFAULT {bool_default}"))
        if "last_morning" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN last_morning {dt_type}"))
        if "last_day" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN last_day {dt_type}"))
        if "last_evening" not in existing:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN last_evening {dt_type}"))

    existing = _column_names("meals")
    with engine.begin() as conn:
        if "type" not in existing:
            conn.execute(text("ALTER TABLE meals ADD COLUMN type TEXT DEFAULT 'meal'"))


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    blocked = Column(Boolean, default=False)

    subscription = relationship(
        'Subscription', back_populates='user', uselist=False, cascade='all, delete-orphan'
    )
    notification = relationship(
        'NotificationStatus', back_populates='user', uselist=False, cascade='all, delete-orphan'
    )
    reminders = relationship(
        'ReminderSettings', back_populates='user', uselist=False, cascade='all, delete-orphan'
    )
    meals = relationship('Meal', back_populates='user')

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
    trial = property(lambda self: self._sub().trial, lambda self, v: setattr(self._sub(), 'trial', v))
    trial_used = property(lambda self: self._sub().trial_used, lambda self, v: setattr(self._sub(), 'trial_used', v))

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

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
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
    trial = Column(Boolean, default=False)
    trial_used = Column(Boolean, default=False)

    user = relationship('User', back_populates='subscription')


class NotificationStatus(Base):
    __tablename__ = 'notification_status'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    notified_7d = Column(Boolean, default=False)
    notified_3d = Column(Boolean, default=False)
    notified_1d = Column(Boolean, default=False)
    notified_0d = Column(Boolean, default=False)
    notified_free = Column(Boolean, default=False)

    user = relationship('User', back_populates='notification')


class ReminderSettings(Base):
    __tablename__ = 'reminders'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
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
class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
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
    user_id = Column(Integer, ForeignKey('users.id'))
    tier = Column(String)
    months = Column(Integer, default=1)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship('User')


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
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

Base.metadata.create_all(engine)
_ensure_columns()
_ensure_options()

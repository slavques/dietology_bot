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
        if "request_limit" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN request_limit INTEGER DEFAULT 20"))
        if "requests_used" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN requests_used INTEGER DEFAULT 0"))
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

    existing = _column_names("meals")
    with engine.begin() as conn:
        if "type" not in existing:
            conn.execute(text("ALTER TABLE meals ADD COLUMN type TEXT DEFAULT 'meal'"))


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    grade = Column(String, default='free')  # 'free', 'paid' or 'pro'
    request_limit = Column(Integer, default=20)
    requests_used = Column(Integer, default=0)
    period_start = Column(DateTime, default=datetime.utcnow)
    period_end = Column(DateTime, nullable=True)
    notified_7d = Column(Boolean, default=False)
    notified_3d = Column(Boolean, default=False)
    notified_1d = Column(Boolean, default=False)
    notified_0d = Column(Boolean, default=False)
    notified_free = Column(Boolean, default=False)
    daily_used = Column(Integer, default=0)
    daily_start = Column(DateTime, default=datetime.utcnow)
    blocked = Column(Boolean, default=False)
    meals = relationship('Meal', back_populates='user')

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


class Option(Base):
    __tablename__ = 'options'

    key = Column(String, primary_key=True)
    value = Column(String)


def get_option(key: str, default: str | None = None) -> str | None:
    session = SessionLocal()
    row = session.query(Option).filter_by(key=key).first()
    result = row.value if row else default
    session.close()
    return result


def get_option_bool(key: str, default: bool = True) -> bool:
    val = get_option(key, "1" if default else "0")
    return str(val) == "1"


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

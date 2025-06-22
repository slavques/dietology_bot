from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def _column_names(table: str) -> set[str]:
    """Return existing column names for given table."""
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
    return {row["name"] for row in rows}


def _ensure_columns():
    """Add new columns to old databases if they are missing."""
    existing = _column_names("users")
    with engine.begin() as conn:
        if "grade" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN grade TEXT DEFAULT 'free'"))
        if "request_limit" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN request_limit INTEGER DEFAULT 20"))
        if "requests_used" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN requests_used INTEGER DEFAULT 0"))
        if "period_start" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN period_start DATETIME"))
        if "period_end" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN period_end DATETIME"))
        if "notified_7d" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN notified_7d BOOLEAN DEFAULT 0"))
        if "notified_3d" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN notified_3d BOOLEAN DEFAULT 0"))
        if "notified_0d" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN notified_0d BOOLEAN DEFAULT 0"))


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    grade = Column(String, default='free')  # 'free' or 'paid'
    request_limit = Column(Integer, default=20)
    requests_used = Column(Integer, default=0)
    period_start = Column(DateTime, default=datetime.utcnow)
    period_end = Column(DateTime, nullable=True)
    notified_7d = Column(Boolean, default=False)
    notified_3d = Column(Boolean, default=False)
    notified_0d = Column(Boolean, default=False)
    meals = relationship('Meal', back_populates='user')

class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String)
    ingredients = Column(String)
    serving = Column(Float)
    calories = Column(Float)
    protein = Column(Float)
    fat = Column(Float)
    carbs = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship('User', back_populates='meals')

Base.metadata.create_all(engine)
_ensure_columns()

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import Base, engine, SessionLocal, User, Goal, Meal  # noqa: E402
from bot.reminders import _goal_meal_window  # noqa: E402


Base.metadata.create_all(bind=engine)


@pytest.fixture
def session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _create_user(session, *, telegram_id=1):
    user = User(telegram_id=telegram_id)
    user.timezone = 0
    user.morning_time = "08:00"
    user.evening_time = "20:00"
    user.goal = Goal(
        reminder_morning=True,
        reminder_evening=True,
        calories=2000,
        protein=150,
        fat=60,
        carbs=250,
    )
    session.add(user)
    session.commit()
    return session.query(User).filter_by(telegram_id=telegram_id).one()


def test_evening_window_includes_meals_before_midnight(session):
    user = _create_user(session, telegram_id=101)
    user.last_morning = datetime(2024, 5, 4, 8, 0)
    user.evening_time = "00:20"
    session.commit()

    meals = [
        Meal(user_id=user.id, name="Обед", timestamp=datetime(2024, 5, 4, 12, 0)),
        Meal(user_id=user.id, name="Ужин", timestamp=datetime(2024, 5, 4, 21, 30)),
    ]
    session.add_all(meals)
    session.commit()

    local_now = datetime(2024, 5, 5, 0, 20)
    offset = timedelta(minutes=user.timezone or 0)
    start, end = _goal_meal_window(user.last_morning, local_now, offset, fallback_days=0)

    results = (
        session.query(Meal)
        .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
        .order_by(Meal.timestamp)
        .all()
    )

    assert [m.name for m in results] == ["Обед", "Ужин"]


def test_morning_window_includes_meals_after_evening(session):
    user = _create_user(session, telegram_id=202)
    user.last_morning = datetime(2024, 5, 4, 8, 0)
    user.last_evening = datetime(2024, 5, 4, 23, 50)
    session.commit()

    meals = [
        Meal(user_id=user.id, name="Перекус", timestamp=datetime(2024, 5, 4, 15, 0)),
        Meal(user_id=user.id, name="Поздний ужин", timestamp=datetime(2024, 5, 5, 0, 30)),
    ]
    session.add_all(meals)
    session.commit()

    local_now = datetime(2024, 5, 5, 8, 0)
    offset = timedelta(minutes=user.timezone or 0)
    start, end = _goal_meal_window(user.last_morning, local_now, offset, fallback_days=-1)

    results = (
        session.query(Meal)
        .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
        .order_by(Meal.timestamp)
        .all()
    )

    assert [m.name for m in results] == ["Перекус", "Поздний ужин"]


def test_morning_window_limits_to_last_24_hours(session):
    user = _create_user(session, telegram_id=303)
    user.last_morning = datetime(2024, 5, 2, 8, 0)
    session.commit()

    meals = [
        Meal(user_id=user.id, name="Старый обед", timestamp=datetime(2024, 5, 3, 12, 0)),
        Meal(user_id=user.id, name="Свежий ужин", timestamp=datetime(2024, 5, 4, 21, 0)),
    ]
    session.add_all(meals)
    session.commit()

    local_now = datetime(2024, 5, 5, 8, 0)
    offset = timedelta(minutes=user.timezone or 0)
    start, end = _goal_meal_window(user.last_morning, local_now, offset, fallback_days=-1)

    results = (
        session.query(Meal)
        .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
        .order_by(Meal.timestamp)
        .all()
    )

    assert [m.name for m in results] == ["Свежий ужин"]


def test_evening_window_limits_to_last_24_hours(session):
    user = _create_user(session, telegram_id=404)
    user.last_morning = datetime(2024, 5, 1, 8, 0)
    user.evening_time = "00:20"
    session.commit()

    meals = [
        Meal(user_id=user.id, name="Давний перекус", timestamp=datetime(2024, 5, 2, 22, 0)),
        Meal(user_id=user.id, name="Актуальный ужин", timestamp=datetime(2024, 5, 4, 22, 30)),
    ]
    session.add_all(meals)
    session.commit()

    local_now = datetime(2024, 5, 5, 0, 20)
    offset = timedelta(minutes=user.timezone or 0)
    start, end = _goal_meal_window(user.last_morning, local_now, offset, fallback_days=0)

    results = (
        session.query(Meal)
        .filter(Meal.user_id == user.id, Meal.timestamp >= start, Meal.timestamp < end)
        .order_by(Meal.timestamp)
        .all()
    )

    assert [m.name for m in results] == ["Актуальный ужин"]

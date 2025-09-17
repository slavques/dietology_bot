import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import (  # noqa: E402
    Base,
    engine,
    SessionLocal,
    User,
    Goal,
    Meal,
)
from bot.handlers.goals import goal_summary_text  # noqa: E402


Base.metadata.create_all(bind=engine)


def _create_user_with_goal(session, telegram_id=None):
    if telegram_id is None:
        telegram_id = int(datetime.utcnow().timestamp() * 1_000_000)
        while session.query(User).filter_by(telegram_id=telegram_id).first():
            telegram_id += 1
    user = User(telegram_id=telegram_id)
    session.add(user)
    session.commit()
    goal = Goal(user_id=user.id, calories=2000, protein=150, fat=60, carbs=250)
    user.goal = goal
    session.add(goal)
    session.commit()
    return goal


def test_goal_summary_includes_macro_progress_without_meals():
    session = SessionLocal()
    goal = _create_user_with_goal(session)
    assert goal_summary_text(goal, session) == (
        "🎯 Текущая цель на сегодня\n"
        "Ккал: 2000 | Б: 150 Ж: 60 У: 250\n"
        "Прогресс: 0/2000 | Б: 0/150 Ж: 0/60 У: 0/250"
    )
    session.close()


def test_goal_summary_reflects_saved_meals():
    session = SessionLocal()
    goal = _create_user_with_goal(session)
    meal = Meal(
        user_id=goal.user_id,
        name="Овсянка",
        ingredients="",
        serving=100,
        calories=600,
        protein=30,
        fat=20,
        carbs=80,
        timestamp=datetime.utcnow(),
    )
    session.add(meal)
    session.commit()
    assert goal_summary_text(goal, session) == (
        "🎯 Текущая цель на сегодня\n"
        "Ккал: 2000 | Б: 150 Ж: 60 У: 250\n"
        "Прогресс: 600.0/2000 | Б: 30.0/150 Ж: 20.0/60 У: 80.0/250"
    )
    session.close()

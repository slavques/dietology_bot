import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import Base, engine, SessionLocal, User, Goal, Meal  # noqa: E402
from bot.handlers.goals import goal_trends_report  # noqa: E402


Base.metadata.create_all(bind=engine)


def test_goal_trends_report_averages_meals():
    session = SessionLocal()
    user = User(telegram_id=999)
    session.add(user)
    session.commit()
    goal = Goal(user_id=user.id, calories=2000, protein=100, fat=70, carbs=250)
    user.goal = goal
    session.add(goal)
    session.commit()
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    meal1 = Meal(
        user_id=user.id,
        name="m1",
        ingredients="",
        serving=100,
        calories=1800,
        protein=90,
        fat=60,
        carbs=200,
        timestamp=now - timedelta(days=1),
    )
    meal2 = Meal(
        user_id=user.id,
        name="m2",
        ingredients="",
        serving=100,
        calories=2200,
        protein=110,
        fat=80,
        carbs=260,
        timestamp=now,
    )
    session.add_all([meal1, meal2])
    session.commit()
    text = goal_trends_report(user, 7, session)
    assert text == (
        "📊 Тенденции за 7 дней\n"
        "— Средний баланс: 0 ккал/день\n"
        "— Белки: 100 от цели 100\n"
        "— Жиры: 70 от цели 70\n"
        "— Углеводы: 230 от цели 250\n"
        "Продолжай! 💪"
    )
    session.close()


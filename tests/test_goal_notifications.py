import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import Base, engine, SessionLocal, User, Goal  # noqa: E402
from bot.utils import format_meal_message  # noqa: E402
from bot.handlers.goals import goal_progress_text  # noqa: E402


Base.metadata.create_all(bind=engine)


def test_format_meal_message_warns_on_goal_exceed():
    session = SessionLocal()
    user = User(telegram_id=1)
    user.goal = Goal(calories=100, protein=10, fat=5, carbs=10)
    session.add(user)
    session.commit()
    macros = {"calories": 200, "protein": 20, "fat": 10, "carbs": 15}
    text = format_meal_message("Test", 100, macros, user_id=1)
    assert "превысишь дневную цель" in text
    session.close()


def test_goal_progress_text_outputs_expected_lines():
    goal = Goal(calories=2000, protein=150, fat=60, carbs=250)
    totals = {"calories": 2300, "protein": 160, "fat": 70, "carbs": 260}
    text = goal_progress_text(goal, totals)
    assert "Превышение на 300 ккал" in text

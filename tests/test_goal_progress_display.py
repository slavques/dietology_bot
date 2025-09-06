import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.database import Goal  # noqa: E402
from bot.handlers.goals import goal_summary_text  # noqa: E402


def test_goal_summary_includes_macro_progress():
    goal = Goal(user_id=1, calories=2000, protein=150, fat=60, carbs=250)
    assert goal_summary_text(goal) == (
        "🎯 Текущая цель на сегодня\n"
        "Ккал: 2000 | Б: 150 Ж: 60 У: 250\n"
        "Прогресс: 0/2000 | Б: 0/150 Ж: 0/60 У: 0/250"
    )

import os
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.cleanup import (  # noqa: E402
    PREFIX,
    RETENTION_DAYS,
    STALE_PENDING_SECONDS,
    run_cleanup_cycle,
)
from bot import storage  # noqa: E402


@pytest.fixture(autouse=True)
def clear_pending_meals():
    storage.pending_meals.clear()
    yield
    storage.pending_meals.clear()


def _touch(path: os.PathLike[str], mtime: float) -> None:
    os.utime(path, (mtime, mtime))


def test_run_cleanup_cycle_removes_stale_entries(tmp_path):
    now = 1_000_000.0
    old_file = tmp_path / f"{PREFIX}old.jpg"
    old_file.write_text("data")
    stale_file_time = now - (RETENTION_DAYS * 24 * 3600 + 10)
    _touch(old_file, stale_file_time)

    meal_id = "user_1"
    storage.pending_meals[meal_id] = {
        "timestamp": now - STALE_PENDING_SECONDS - 1,
        "photo_path": str(old_file),
    }

    run_cleanup_cycle(now=now, temp_dir=str(tmp_path))

    assert meal_id not in storage.pending_meals
    assert not old_file.exists()


def test_run_cleanup_cycle_keeps_recent_entries(tmp_path):
    now = 2_000_000.0
    fresh_file = tmp_path / f"{PREFIX}fresh.jpg"
    fresh_file.write_text("data")
    _touch(fresh_file, now - 60)

    meal_id = "user_recent"
    storage.pending_meals[meal_id] = {
        "timestamp": now - 10,
        "photo_path": str(fresh_file),
    }

    run_cleanup_cycle(now=now, temp_dir=str(tmp_path))

    assert meal_id in storage.pending_meals
    assert storage.pending_meals[meal_id]["photo_path"] == str(fresh_file)
    assert fresh_file.exists()


def test_document_prompt_cooldown_and_reset(monkeypatch):
    storage._document_photo_reminders.clear()

    monkeypatch.setattr(storage.time, "time", lambda: 1000.0)
    assert storage.should_send_document_prompt(123, cooldown=10) is True
    assert storage.should_send_document_prompt(123, cooldown=10) is False

    storage.reset_document_prompt(123)
    monkeypatch.setattr(storage.time, "time", lambda: 1005.0)
    assert storage.should_send_document_prompt(123, cooldown=10) is False

    monkeypatch.setattr(storage.time, "time", lambda: 1011.0)
    assert storage.should_send_document_prompt(123, cooldown=10) is True

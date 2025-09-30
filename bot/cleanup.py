import asyncio
import os
import tempfile
import time
from typing import Optional

from .storage import pending_meals, remove_photo_if_unused

PREFIX = "diet_photo_"
RETENTION_DAYS = 7
STALE_PENDING_SECONDS = 3600


def run_cleanup_cycle(*, now: Optional[float] = None, temp_dir: Optional[str] = None) -> None:
    """Perform a single cleanup pass over temp files and pending meals."""

    current_time = now if now is not None else time.time()
    cutoff = current_time - RETENTION_DAYS * 24 * 3600
    directory = temp_dir or tempfile.gettempdir()

    for name in os.listdir(directory):
        if not name.startswith(PREFIX):
            continue
        path = os.path.join(directory, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    stale_cutoff = current_time - STALE_PENDING_SECONDS
    for meal_id, meal in list(pending_meals.items()):
        timestamp = meal.get("timestamp")
        path = meal.get("photo_path")
        if timestamp and timestamp < stale_cutoff:
            if path:
                remove_photo_if_unused(path, ignore_id=meal_id)
            pending_meals.pop(meal_id, None)


def cleanup_watcher(check_interval: int = 60):
    async def _cleanup():
        while True:
            run_cleanup_cycle()
            await asyncio.sleep(check_interval)

    return _cleanup

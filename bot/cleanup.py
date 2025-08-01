import asyncio
import os
import tempfile
import time
from .storage import pending_meals, remove_photo_if_unused

PREFIX = "diet_photo_"
RETENTION_DAYS = 7


def cleanup_watcher(check_interval: int = 60):
    async def _cleanup():
        while True:
            now = time.time()
            cutoff = now - RETENTION_DAYS * 24 * 3600
            temp_dir = tempfile.gettempdir()
            for name in os.listdir(temp_dir):
                if name.startswith(PREFIX):
                    path = os.path.join(temp_dir, name)
                    try:
                        if os.path.getmtime(path) < cutoff:
                            os.remove(path)
                    except FileNotFoundError:
                        pass
                    except Exception:
                        pass
            # remove stale photos from pending meals
            stale = now - 3600
            for mid, meal in list(pending_meals.items()):
                ts = meal.get("timestamp")
                path = meal.get("photo_path")
                if path and ts and ts < stale:
                    remove_photo_if_unused(path, mid)
                    meal["photo_path"] = None
            await asyncio.sleep(check_interval)
    return _cleanup

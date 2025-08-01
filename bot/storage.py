from typing import Dict
import os


# in-memory store for photos being processed
pending_meals: Dict[str, Dict] = {}


def remove_photo_if_unused(path: str, ignore_id: str | None = None) -> None:
    """Delete the photo from disk if no other pending meal references it."""
    if not path:
        return
    for mid, meal in pending_meals.items():
        if mid != ignore_id and meal.get("photo_path") == path:
            return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        pass


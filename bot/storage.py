from typing import Dict, Optional
import os
import time


# in-memory store for photos being processed
pending_meals: Dict[str, Dict] = {}

# track when we last reminded a user about document photo uploads
_document_photo_reminders: Dict[int, float] = {}


def should_send_document_prompt(user_id: int, cooldown: int = 300) -> bool:
    """Return True if we should remind the user to send regular photo uploads."""

    now = time.time()
    last_shown = _document_photo_reminders.get(user_id)
    if last_shown and now - last_shown < cooldown:
        return False
    _document_photo_reminders[user_id] = now
    return True


def remove_photo_if_unused(path: str, ignore_id: Optional[str] = None) -> None:
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


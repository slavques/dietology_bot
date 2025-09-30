from __future__ import annotations

from typing import Dict, Optional, Union
import os
import time


# in-memory store for photos being processed
pending_meals: Dict[str, Dict] = {}

# track reminder states for invalid photo uploads
_ReminderState = Dict[str, Union[float, bool]]
_document_photo_reminders: Dict[int, _ReminderState] = {}
_multi_photo_reminders: Dict[int, _ReminderState] = {}


def _should_send_prompt(
    store: Dict[int, _ReminderState], user_id: int, cooldown: int
) -> bool:
    """Return True if a prompt should be shown, locking it until reset."""

    now = time.time()
    state = store.get(user_id)
    if state:
        if state.get("locked"):
            return False
        last_sent = float(state.get("last_sent", 0.0))
        if now - last_sent < cooldown:
            return False
    store[user_id] = {"last_sent": now, "locked": True}
    return True


def _reset_prompt(store: Dict[int, _ReminderState], user_id: int) -> None:
    state = store.get(user_id)
    if state:
        state["locked"] = False


def should_send_document_prompt(user_id: int, cooldown: int = 300) -> bool:
    """Return True if we should remind the user to send regular photo uploads."""

    return _should_send_prompt(_document_photo_reminders, user_id, cooldown)


def reset_document_prompt(user_id: int) -> None:
    """Allow the next document reminder for the given user."""

    _reset_prompt(_document_photo_reminders, user_id)


def should_send_multi_photo_prompt(user_id: int, cooldown: int = 300) -> bool:
    """Return True if we should warn the user about multiple photo uploads."""

    return _should_send_prompt(_multi_photo_reminders, user_id, cooldown)


def reset_multi_photo_prompt(user_id: int) -> None:
    """Allow the next multiple photo reminder for the given user."""

    _reset_prompt(_multi_photo_reminders, user_id)


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


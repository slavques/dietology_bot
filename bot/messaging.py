"""Utilities for reliable message delivery to Telegram users."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from .logger import log


@dataclass
class DeliveryReport:
    """Result of sending a message to multiple users."""

    total: int
    delivered: int
    failed: list[int]

    @property
    def has_failures(self) -> bool:
        return bool(self.failed)


async def _send_with_retries(
    bot: Bot,
    chat_id: int,
    *,
    text: str,
    category: str,
    retries: int = 3,
    base_delay: float = 0.5,
    **kwargs,
) -> bool:
    """Send a message handling transient Telegram errors."""

    attempt = 0
    delay = base_delay
    last_error: Exception | None = None
    while attempt < retries:
        attempt += 1
        try:
            await bot.send_message(chat_id, text, **kwargs)
            return True
        except TelegramRetryAfter as exc:  # pragma: no cover - depends on Telegram
            last_error = exc
            wait_time = exc.retry_after + 0.5
            log(
                category,
                "retry after %ss for %s (attempt %s/%s)",
                exc.retry_after,
                chat_id,
                attempt,
                retries,
            )
            await asyncio.sleep(wait_time)
        except TelegramAPIError as exc:  # pragma: no cover - depends on Telegram
            last_error = exc
            log(category, "telegram api error for %s: %s", chat_id, exc)
            break
        except Exception as exc:  # pragma: no cover - unexpected errors
            last_error = exc
            log(
                category,
                "unexpected error for %s: %s (attempt %s/%s)",
                chat_id,
                exc,
                attempt,
                retries,
            )
            await asyncio.sleep(delay)
            delay *= 2
    if last_error:
        log(
            category,
            "failed to deliver message to %s after %s attempts: %s",
            chat_id,
            retries,
            last_error,
        )
    else:
        log(category, "failed to deliver message to %s", chat_id)
    return False


async def send_with_retries(
    bot: Bot,
    chat_id: int,
    *,
    text: str,
    category: str,
    retries: int = 3,
    **kwargs,
) -> bool:
    """Public wrapper to send a message with retry logic."""

    return await _send_with_retries(
        bot,
        chat_id,
        text=text,
        category=category,
        retries=retries,
        **kwargs,
    )


async def deliver_text(
    bot: Bot,
    user_ids: Iterable[int],
    *,
    text: str,
    category: str,
    retries: int = 3,
    throttle: float = 0.0,
    **kwargs,
) -> DeliveryReport:
    """Send text to every ``user_id`` and return delivery statistics."""

    failed: list[int] = []
    delivered = 0
    ids: Sequence[int] = list(user_ids)
    for index, user_id in enumerate(ids, start=1):
        success = await _send_with_retries(
            bot,
            user_id,
            text=text,
            category=category,
            retries=retries,
            **kwargs,
        )
        if success:
            delivered += 1
        else:
            failed.append(user_id)
        if throttle and index < len(ids):
            await asyncio.sleep(throttle)
    return DeliveryReport(total=len(ids), delivered=delivered, failed=failed)

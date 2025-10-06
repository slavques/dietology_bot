"""Helpers for discount notifications."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .database import Payment, User


def determine_discount_type(
    session: Session,
    user: User,
    decision_time: datetime,
    *,
    respect_cooldown: bool = True,
    skip_inactive: bool = True,
) -> Optional[str]:
    """Return discount type to send to the user.

    The result is one of ``"new"`` (no payments yet) or ``"return"`` (had
    payments in the past) or ``None`` if the user should not receive a discount
    message at this time.
    """

    subscription = user.subscription
    if not subscription:
        return None

    trial_end = subscription.trial_end
    trial_ended = bool(trial_end and trial_end <= decision_time)

    if subscription.trial:
        if not trial_ended:
            # Active trial – do not send a discount yet.
            return None
    else:
        # If the trial flag is already cleared but the end date is still in the
        # future, treat it as active as well.
        if trial_end and trial_end > decision_time:
            return None

    if subscription.grade != "free" and not trial_ended:
        return None

    if skip_inactive and (user.blocked or user.left_bot):
        return None

    engagement = user.engagement
    if respect_cooldown and engagement and engagement.discount_sent:
        last_sent_at = engagement.discount_last_sent
        if not last_sent_at and engagement.discount_expires:
            last_sent_at = engagement.discount_expires - timedelta(days=1)
        if last_sent_at and last_sent_at > decision_time - timedelta(days=30):
            return None

    payments = (
        session.query(Payment)
        .filter_by(user_id=user.id)
        .order_by(Payment.timestamp.asc())
        .all()
    )
    if not payments:
        if user.created_at and user.created_at <= decision_time - timedelta(days=3):
            return "new"
        return None

    paid_until: Optional[datetime] = None
    for payment in payments:
        months = payment.months or 1
        if months <= 0:
            months = 1
        start = payment.timestamp
        if paid_until and paid_until > start:
            start = paid_until
        paid_until = start + timedelta(days=30 * months)
    if not paid_until or paid_until > decision_time - timedelta(days=3):
        return None
    return "return"


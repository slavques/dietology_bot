from aiogram import types, Dispatcher, F

from ..texts import (
    REFERRAL_INTRO,
    REFERRAL_STATS,
    REFERRAL_FRIEND_ACTIVATED,
    REFERRAL_FRIEND_PAID,
)
from ..keyboards import referral_inline_kb
from ..database import get_option_bool, SessionLocal
from ..subscriptions import ensure_user, add_subscription_days, start_trial


def _grant_days(session: SessionLocal, user, days: int) -> None:
    """Give referral bonus days to a user."""
    if user.grade in {"light", "pro"} and not user.trial:
        add_subscription_days(session, user, days)
    else:
        start_trial(session, user, days, "light")


async def reward_first_analysis(bot, session: SessionLocal, user) -> None:
    """Reward the referrer when invitee makes their first request."""
    if not get_option_bool("feat_referral") or not user.referrer_id:
        return
    if user.requests_total != 1:
        return
    referrer = ensure_user(session, user.referrer_id)
    _grant_days(session, referrer, 5)
    try:
        await bot.send_message(user.referrer_id, REFERRAL_FRIEND_ACTIVATED)
    except Exception:
        pass


async def reward_subscription(
    bot, session: SessionLocal, user, payments: int
) -> None:
    """Reward the referrer when invitee buys a subscription."""
    if not get_option_bool("feat_referral") or not user.referrer_id:
        return
    if payments != 1:
        return
    referrer = ensure_user(session, user.referrer_id)
    _grant_days(session, referrer, 30)
    try:
        await bot.send_message(user.referrer_id, REFERRAL_FRIEND_PAID)
    except Exception:
        pass

async def _referral_link(bot, user_id: int) -> str:
    me = await bot.get_me()
    return f"https://t.me/{me.username}?start=ref_{user_id}"

async def cb_referral(query: types.CallbackQuery):
    link = await _referral_link(query.bot, query.from_user.id)
    text = REFERRAL_INTRO.format(link=link)
    await query.message.edit_text(text, parse_mode="HTML")
    await query.message.edit_reply_markup(reply_markup=referral_inline_kb(link))
    await query.answer()

async def cb_referral_stats(query: types.CallbackQuery):
    link = await _referral_link(query.bot, query.from_user.id)
    # placeholders for future implementation
    count = 0
    days = 0
    text = REFERRAL_STATS.format(count=count, days=days)
    await query.message.edit_text(text, parse_mode="HTML")
    await query.message.edit_reply_markup(reply_markup=referral_inline_kb(link))
    await query.answer()


def register(dp: Dispatcher):
    dp.callback_query.register(cb_referral, F.data == "referral")
    dp.callback_query.register(cb_referral_stats, F.data == "referral:stats")

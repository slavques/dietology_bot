from aiogram import types, Dispatcher, F
from ..texts import REFERRAL_INTRO, REFERRAL_STATS
from ..keyboards import referral_inline_kb

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

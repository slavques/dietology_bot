from ..settings import PLAN_PRICES, PRO_PLAN_PRICES, DISCOUNT_PLAN_PRICES
from aiogram import types, Dispatcher, F, Bot
from aiogram.fsm.context import FSMContext
from datetime import datetime

from ..database import SessionLocal, Payment
from ..subscriptions import ensure_user, process_payment_success, notify_trial_end
from ..alerts import subscription_paid as alert_subscription_paid
from ..keyboards import (
    pay_kb,
    back_menu_kb,
    payment_method_inline,
    subscription_plans_inline_kb,
    subscription_grades_inline_kb,
)
from ..config import YOOKASSA_TOKEN
from aiogram.types import LabeledPrice
from ..texts import (
    INTRO_BASE,
    PLAN_TEXT,
    SUB_INVALID_PLAN,
    SUB_METHOD_TEXT,
    SUB_SUCCESS,
    SUB_CANCELLED,
    BTN_SUBSCRIPTION,
    PLAN_TITLE_1M,
    PLAN_TITLE_3M,
    PLAN_TITLE_6M,
    BTN_PRO_MODE,
    BTN_LIGHT_MODE,
    INVOICE_LABEL,
    INVOICE_TITLE,
)
from ..logger import log



def build_intro_text(user) -> str:
    from ..database import get_option_bool

    if user.grade == "pro":
        plan = "<b>⚡ Pro-режим</b>"
    elif user.grade == "light":
        plan = "<b>🔸 Старт</b>"
    else:
        plan = "Не подключено"

    lines = [INTRO_BASE.format(plan=plan)]
    if get_option_bool("grade_light"):
        lines.append("\n<b>🔸 Старт</b>\nБазовый анализ, примерная \nточность, минимум усилий")
    if get_option_bool("grade_pro"):
        lines.append("<b>⚡ Pro-режим</b>\nУлучшенная модель, высокая точность, \nумный расчёт")
    return "\n".join(lines)


async def cb_pay(query: types.CallbackQuery):
    """Send an invoice via YooKassa when the user presses the pay button."""
    _, tier, code = query.data.split(":", 2)
    if code not in {"1m", "3m", "6m"}:
        await query.message.answer(
            SUB_INVALID_PLAN
        )
        await query.answer()
        return
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    discount = (
        user.engagement
        and user.engagement.discount_expires
        and user.engagement.discount_expires > datetime.utcnow()
    )
    session.close()
    title_map = {"1m": PLAN_TITLE_1M, "3m": PLAN_TITLE_3M, "6m": PLAN_TITLE_6M}
    price_map = (
        DISCOUNT_PLAN_PRICES
        if discount and tier == "light"
        else (PLAN_PRICES if tier == "light" else PRO_PLAN_PRICES)
    )
    title = title_map[code]
    amount = price_map[code] * 100
    payload = f"{tier}:{code}"
    price = LabeledPrice(label=INVOICE_LABEL, amount=amount)
    await query.bot.send_invoice(
        chat_id=query.from_user.id,
        title=INVOICE_TITLE,
        description=title,
        payload=payload,
        provider_token=YOOKASSA_TOKEN,
        currency="RUB",
        prices=[price],
    )
    log("payment", "invoice sent to %s for %s", query.from_user.id, payload)
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()


async def show_subscription_menu(message: types.Message):
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    text = build_intro_text(user)
    session.close()
    await message.answer(text, reply_markup=subscription_grades_inline_kb(), parse_mode="HTML")


async def cb_subscribe(query: types.CallbackQuery, state: FSMContext):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    await notify_trial_end(query.bot, session, user)
    text = build_intro_text(user)
    session.close()
    await query.message.edit_text(text, parse_mode="HTML")
    await query.message.edit_reply_markup(reply_markup=subscription_grades_inline_kb())
    await state.clear()
    await query.answer()


async def cb_grade(query: types.CallbackQuery):
    tier = query.data.split(":", 1)[1]
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    discount = (
        user.engagement
        and user.engagement.discount_expires
        and user.engagement.discount_expires > datetime.utcnow()
    )
    session.close()
    grade = "🔸 Старт" if tier == "light" else "⚡ Pro-режим"
    await query.message.edit_text(
        PLAN_TEXT.format(grade=grade),
        reply_markup=subscription_plans_inline_kb(tier, discount=discount),
        parse_mode="HTML",
    )
    await query.answer()




async def cb_plan(query: types.CallbackQuery):
    _, tier, code = query.data.split(":", 2)
    grade = "🔸 Старт" if tier == "light" else "⚡ Pro-режим"
    await query.message.edit_text(
        PLAN_TEXT.format(grade=grade),
        reply_markup=payment_method_inline(code, tier, include_back=True),
        parse_mode="HTML",
    )
    await query.answer()


async def cb_method(query: types.CallbackQuery):
    _, tier, code = query.data.split(":", 2)
    TITLE_MAP = {"1m": PLAN_TITLE_1M, "3m": PLAN_TITLE_3M, "6m": PLAN_TITLE_6M}
    plan = TITLE_MAP.get(code, "")
    await query.message.edit_text(
        SUB_METHOD_TEXT.format(plan=plan),
        reply_markup=pay_kb(code, tier, include_back=True),
        parse_mode="HTML",
    )
    await query.answer()


async def cb_method_back(query: types.CallbackQuery):
    _, tier, code = query.data.split(":", 2)
    grade = "🔸 Старт" if tier == "light" else "⚡ Pro-режим"
    await query.message.edit_text(
        PLAN_TEXT.format(grade=grade),
        reply_markup=payment_method_inline(code, tier, include_back=True),
        parse_mode="HTML",
    )
    await query.answer()


async def cb_plan_back(query: types.CallbackQuery):
    tier = query.data.split(":", 1)[1]
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    discount = (
        user.engagement
        and user.engagement.discount_expires
        and user.engagement.discount_expires > datetime.utcnow()
    )
    session.close()
    grade = "🔸 Старт" if tier == "light" else "⚡ Pro-режим"
    await query.message.edit_text(
        PLAN_TEXT.format(grade=grade),
        reply_markup=subscription_plans_inline_kb(tier, discount=discount),
        parse_mode="HTML",
    )
    await query.answer()


async def cb_sub_plans(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    await notify_trial_end(query.bot, session, user)
    text = build_intro_text(user)
    session.close()
    await query.message.edit_text(text, parse_mode="HTML")
    await query.message.edit_reply_markup(reply_markup=subscription_grades_inline_kb())
    await query.answer()

async def handle_pre_checkout(query: types.PreCheckoutQuery, bot: Bot):
    """Confirm pre-checkout query from Telegram."""
    await bot.answer_pre_checkout_query(query.id, ok=True)


async def handle_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    tier, code = payload.split(":")
    months = {"1m": 1, "3m": 3, "6m": 6}.get(code, 1)
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    process_payment_success(session, user, months, grade=tier)
    count = session.query(Payment).filter_by(user_id=user.id).count()
    session.close()
    grade_name = "🔸 Старт" if tier == "light" else "⚡ Pro-режим"
    await alert_subscription_paid(user.telegram_id, count, grade_name, months)
    # Don't delete the invoice message here so Telegram can replace it
    # with the service notification that confirms the payment.
    await message.answer(
        SUB_SUCCESS,
        reply_markup=back_menu_kb(),
    )
    log("payment", "successful payment from %s", message.from_user.id)


def register(dp: Dispatcher):
    dp.message.register(show_subscription_menu, F.text == BTN_SUBSCRIPTION)
    dp.callback_query.register(cb_subscribe, F.data == "subscribe")
    dp.callback_query.register(cb_grade, F.data.startswith("grade:"))
    dp.callback_query.register(cb_plan, F.data.startswith("plan:"))
    dp.callback_query.register(cb_plan_back, F.data.startswith("plan_back:"))
    dp.callback_query.register(cb_sub_plans, F.data == "sub_grades")
    dp.callback_query.register(cb_method_back, F.data.startswith("method_back:"))
    dp.callback_query.register(cb_method, F.data.startswith("method:"))
    dp.callback_query.register(cb_pay, F.data.startswith("pay:"))
    dp.pre_checkout_query.register(handle_pre_checkout)
    dp.message.register(handle_successful_payment, F.successful_payment)

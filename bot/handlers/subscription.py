from ..settings import PLAN_PRICES, PRO_PLAN_PRICES
from aiogram import types, Dispatcher, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from ..database import SessionLocal
from ..subscriptions import ensure_user, process_payment_success, _daily_check
from ..keyboards import (
    subscription_plans_kb,
    pay_kb,
    back_menu_kb,
    payment_method_inline,
    subscription_plans_inline_kb,
    subscription_grades_inline_kb,
    menu_inline_kb,
)
from ..config import YOOKASSA_TOKEN
from aiogram.types import LabeledPrice
from ..texts import (
    INTRO_TEXT,
    PLAN_TEXT,
    SUB_INVALID_PLAN,
    SUB_METHOD_TEXT,
    SUB_SUCCESS,
    SUB_CANCELLED,
    NOTIFY_SENT,
    BTN_SUBSCRIPTION,
    BTN_BACK_TEXT,
    BTN_PLAN_1M,
    BTN_PLAN_3M,
    BTN_PLAN_6M,
    PLAN_TITLE_1M,
    PLAN_TITLE_3M,
    PLAN_TITLE_6M,
    BTN_PRO_MODE,
    BTN_LIGHT_MODE,
    INVOICE_LABEL,
    INVOICE_TITLE,
)
from ..logger import log

SUCCESS_CMD = "success1467"
REFUSED_CMD = "refused1467"
NOTIFY_CMD = "notify1467"

# map subscription plans to invoice details
LIGHT_PLAN_MAP = {
    "1m": (PLAN_TITLE_1M, PLAN_PRICES['1m'] * 100, 1),
    "3m": (PLAN_TITLE_3M, PLAN_PRICES['3m'] * 100, 3),
    "6m": (PLAN_TITLE_6M, PLAN_PRICES['6m'] * 100, 6),
}
PRO_PLAN_MAP = {
    "1m": (PLAN_TITLE_1M, PRO_PLAN_PRICES['1m'] * 100, 1),
    "3m": (PLAN_TITLE_3M, PRO_PLAN_PRICES['3m'] * 100, 3),
    "6m": (PLAN_TITLE_6M, PRO_PLAN_PRICES['6m'] * 100, 6),
}


async def cb_pay(query: types.CallbackQuery):
    """Send an invoice via YooKassa when the user presses the pay button."""
    _, tier, code = query.data.split(":", 2)
    if code not in {"1m", "3m", "6m"}:
        await query.message.answer(
            SUB_INVALID_PLAN
        )
        await query.answer()
        return
    plan_map = LIGHT_PLAN_MAP if tier == "light" else PRO_PLAN_MAP
    title, amount, months = plan_map[code]
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
    await message.answer(INTRO_TEXT, reply_markup=subscription_grades_inline_kb())


async def cb_subscribe(query: types.CallbackQuery, state: FSMContext):
    await query.message.edit_text(INTRO_TEXT)
    await query.message.edit_reply_markup(reply_markup=subscription_grades_inline_kb())
    await state.clear()
    await query.answer()


async def cb_grade(query: types.CallbackQuery):
    tier = query.data.split(":", 1)[1]
    await query.message.edit_text(
        PLAN_TEXT,
        reply_markup=subscription_plans_inline_kb(tier),
    )
    await query.answer()




async def cb_plan(query: types.CallbackQuery):
    _, tier, code = query.data.split(":", 2)
    await query.message.edit_text(
        PLAN_TEXT,
        reply_markup=payment_method_inline(code, tier, include_back=True),
    )
    await query.answer()


async def cb_method(query: types.CallbackQuery):
    _, tier, code = query.data.split(":", 2)
    TITLE_MAP = {"1m": PLAN_TITLE_1M, "3m": PLAN_TITLE_3M, "6m": PLAN_TITLE_6M}
    plan = TITLE_MAP.get(code, "")
    await query.message.edit_text(
        SUB_METHOD_TEXT.format(plan=plan),
        reply_markup=pay_kb(code, tier, include_back=True),
    )
    await query.answer()


async def cb_method_back(query: types.CallbackQuery):
    _, tier, code = query.data.split(":", 2)
    await query.message.edit_text(
        PLAN_TEXT,
        reply_markup=payment_method_inline(code, tier, include_back=True),
    )
    await query.answer()


async def cb_plan_back(query: types.CallbackQuery):
    tier = query.data.split(":", 1)[1]
    await query.message.edit_text(
        PLAN_TEXT,
        reply_markup=subscription_plans_inline_kb(tier),
    )
    await query.answer()


async def cb_sub_plans(query: types.CallbackQuery):
    await query.message.edit_text(INTRO_TEXT)
    await query.message.edit_reply_markup(reply_markup=subscription_grades_inline_kb())
    await query.answer()

async def cmd_success(message: types.Message):
    if not message.text.startswith(f"/{SUCCESS_CMD}"):
        return
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    process_payment_success(session, user)
    session.close()
    await message.answer(SUB_SUCCESS)
    log("payment", "manual success command by %s", message.from_user.id)

async def cmd_refused(message: types.Message):
    if not message.text.startswith(f"/{REFUSED_CMD}"):
        return
    await message.answer(SUB_CANCELLED)
    log("payment", "payment refused by %s", message.from_user.id)


async def handle_pre_checkout(query: types.PreCheckoutQuery, bot: Bot):
    """Confirm pre-checkout query from Telegram."""
    await bot.answer_pre_checkout_query(query.id, ok=True)


async def handle_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    tier, code = payload.split(":")
    months = {"1m": 1, "3m": 3, "6m": 6}.get(code, 1)
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    process_payment_success(session, user, months, grade=tier)
    session.close()
    # Don't delete the invoice message here so Telegram can replace it
    # with the service notification that confirms the payment.
    await message.answer(
        SUB_SUCCESS,
        reply_markup=back_menu_kb(),
    )
    log("payment", "successful payment from %s", message.from_user.id)


async def cmd_notify(message: types.Message):
    if not message.text.startswith(f"/{NOTIFY_CMD}"):
        return
    await _daily_check(message.bot)
    await message.answer(NOTIFY_SENT)
    log("notification", "manual notify triggered by %s", message.from_user.id)


def register(dp: Dispatcher):
    dp.message.register(cmd_success, Command(SUCCESS_CMD))
    dp.message.register(cmd_refused, Command(REFUSED_CMD))
    dp.message.register(cmd_notify, Command(NOTIFY_CMD))
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

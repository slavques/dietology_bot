from ..settings import PLAN_PRICES
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
    INVOICE_LABEL,
    INVOICE_TITLE,
)

SUCCESS_CMD = "success1467"
REFUSED_CMD = "refused1467"
NOTIFY_CMD = "notify1467"

# map subscription plans to invoice details
PLAN_MAP = {
    BTN_PLAN_1M.format(price=PLAN_PRICES['1m']): (PLAN_TITLE_1M, PLAN_PRICES['1m'] * 100, 1),
    BTN_PLAN_3M.format(price=PLAN_PRICES['3m']): (PLAN_TITLE_3M, PLAN_PRICES['3m'] * 100, 3),
    BTN_PLAN_6M.format(price=PLAN_PRICES['6m']): (PLAN_TITLE_6M, PLAN_PRICES['6m'] * 100, 6),
}
PLAN_CODES = {
    BTN_PLAN_1M.format(price=PLAN_PRICES['1m']): "1m",
    BTN_PLAN_3M.format(price=PLAN_PRICES['3m']): "3m",
    BTN_PLAN_6M.format(price=PLAN_PRICES['6m']): "6m",
}
PLAN_DISPLAY = {v: k.split(" ", 1)[1] for k, v in PLAN_CODES.items()}


async def cb_pay(query: types.CallbackQuery):
    """Send an invoice via YooKassa when the user presses the pay button."""
    parts = query.data.split(":", 1)
    code = parts[1] if len(parts) > 1 else None
    if not code or code not in {"1m", "3m", "6m"}:
        await query.message.answer(
            SUB_INVALID_PLAN
        )
        await query.answer()
        return
    plan_text = next(key for key, val in PLAN_CODES.items() if val == code)
    title, amount, months = PLAN_MAP[plan_text]
    price = LabeledPrice(label=INVOICE_LABEL, amount=amount)
    await query.bot.send_invoice(
        chat_id=query.from_user.id,
        title=INVOICE_TITLE,
        description=title,
        payload=code,
        provider_token=YOOKASSA_TOKEN,
        currency="RUB",
        prices=[price],
    )
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()


async def show_subscription_menu(message: types.Message):
    await message.answer(INTRO_TEXT, reply_markup=subscription_plans_kb())


async def cb_subscribe(query: types.CallbackQuery, state: FSMContext):
    try:
        await query.message.delete()
    except Exception:
        pass
    await show_subscription_menu(query.message)
    await state.clear()
    await query.answer()


async def choose_plan(message: types.Message, state: FSMContext):
    options = {
        BTN_PLAN_1M.format(price=PLAN_PRICES['1m']),
        BTN_PLAN_3M.format(price=PLAN_PRICES['3m']),
        BTN_PLAN_6M.format(price=PLAN_PRICES['6m']),
    }
    if message.text not in options:
        return
    code = PLAN_CODES.get(message.text)
    await message.answer(
        PLAN_TEXT,
        reply_markup=payment_method_inline(code),
    )


async def cb_method(query: types.CallbackQuery):
    parts = query.data.split(":", 1)
    code = parts[1] if len(parts) > 1 else ""
    plan = PLAN_DISPLAY.get(code, "")
    await query.message.edit_text(
        SUB_METHOD_TEXT.format(plan=plan),
        reply_markup=pay_kb(code),
    )
    await query.answer()

async def cmd_success(message: types.Message):
    if not message.text.startswith(f"/{SUCCESS_CMD}"):
        return
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    process_payment_success(session, user)
    session.close()
    await message.answer(SUB_SUCCESS)

async def cmd_refused(message: types.Message):
    if not message.text.startswith(f"/{REFUSED_CMD}"):
        return
    await message.answer(SUB_CANCELLED)


async def handle_pre_checkout(query: types.PreCheckoutQuery, bot: Bot):
    """Confirm pre-checkout query from Telegram."""
    await bot.answer_pre_checkout_query(query.id, ok=True)


async def handle_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    months = {"1m": 1, "3m": 3, "6m": 6}.get(payload, 1)
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    process_payment_success(session, user, months)
    session.close()
    await message.delete()
    await message.answer(
        SUB_SUCCESS,
        reply_markup=back_menu_kb(),
    )


async def cmd_notify(message: types.Message):
    if not message.text.startswith(f"/{NOTIFY_CMD}"):
        return
    await _daily_check(message.bot)
    await message.answer(NOTIFY_SENT)


def register(dp: Dispatcher):
    dp.message.register(cmd_success, Command(SUCCESS_CMD))
    dp.message.register(cmd_refused, Command(REFUSED_CMD))
    dp.message.register(cmd_notify, Command(NOTIFY_CMD))
    dp.message.register(show_subscription_menu, F.text == BTN_SUBSCRIPTION)
    dp.message.register(
        choose_plan,
        F.text.in_(
            {
                BTN_PLAN_1M.format(price=PLAN_PRICES['1m']),
                BTN_PLAN_3M.format(price=PLAN_PRICES['3m']),
                BTN_PLAN_6M.format(price=PLAN_PRICES['6m']),
            }
        ),
    )
    dp.message.register(show_subscription_menu, F.text == BTN_BACK_TEXT)
    dp.callback_query.register(cb_method, F.data.startswith("method:"))
    dp.callback_query.register(cb_pay, F.data.startswith("pay"))
    dp.pre_checkout_query.register(handle_pre_checkout)
    dp.message.register(handle_successful_payment, F.successful_payment)
    dp.callback_query.register(cb_subscribe, F.data == "subscribe")

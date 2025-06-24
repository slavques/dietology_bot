from datetime import datetime
from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from ..database import SessionLocal
from ..subscriptions import ensure_user, process_payment_success, _daily_check
from ..keyboards import (
    subscription_plans_kb,
    payment_methods_kb,
    subscribe_button,
    pay_kb,
    back_menu_kb,
)
from ..states import SubscriptionState

SUCCESS_CMD = "success1467"
REFUSED_CMD = "refused1467"
NOTIFY_CMD = "notify1467"

INTRO_TEXT = (
    "🍞 Разблокируй ритм!\n\n"
    "Не считай запросы.\n"
    "Не сбивайся.\n"
    "Просто продолжай — в том же темпе.\n"
    "Оставь еду под контролем — без лишнего напряга.\n\n"
    "📉 Чем дольше срок — тем ниже цена!\n"
    " Подключение и оплата — в пару кликов."
)

PLAN_TEXT = (
    "🫶 Спасибо за доверие!\n\n"
    "Ты на шаг ближе к понятному, стабильному и осознанному питанию — без пауз и ограничений.\n\n"
    "Мы постарались сделать оплату простой и быстрой.\n\n"
    "👇 Выбери удобный способ, чтобы бот продолжал считать КБЖУ по каждому фото:"
)


async def cb_pay(query: types.CallbackQuery):
    """Show payment instructions."""
    await query.message.answer(
        "Чтобы оформить подписку, используйте команду /success1467 или свяжитесь с поддержкой."
    )
    await query.answer()


async def show_subscription_menu(message: types.Message):
    await message.answer(INTRO_TEXT, reply_markup=subscription_plans_kb())


async def cb_subscribe(query: types.CallbackQuery, state: FSMContext):
    await show_subscription_menu(query.message)
    await state.clear()
    await query.answer()


async def choose_plan(message: types.Message, state: FSMContext):
    if message.text not in {"🚶‍♂️1 месяц - 149₽", "🏃‍♂️3 месяца - 399₽", "🧘‍♂️6 месяцев - 799₽"}:
        return
    await state.set_state(SubscriptionState.choosing_method)
    await state.update_data(plan=message.text)
    await message.answer(PLAN_TEXT, reply_markup=payment_methods_kb())


async def choose_method(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await state.clear()
        await show_subscription_menu(message)
        return
    if message.text not in {"💳 Банковская карта", "✨Telegram Stars", "🪙Crypto"}:
        return
    data = await state.get_data()
    plan = data.get("plan", "")
    text = (
        "Создали запрос на покупку.\n"
        f"{message.text}\n"
        f"({plan})\n\n"
        "Оплата доступна по кнопке \"Оплатить\" \ud83d\udc47"
    )
    await message.answer(text, reply_markup=pay_kb())
    await message.answer("", reply_markup=back_menu_kb())
    await state.clear()

async def cmd_success(message: types.Message):
    if not message.text.startswith(f"/{SUCCESS_CMD}"):
        return
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    process_payment_success(session, user)
    session.close()
    await message.answer("Оплата принята. Подписка активирована.")

async def cmd_refused(message: types.Message):
    if not message.text.startswith(f"/{REFUSED_CMD}"):
        return
    await message.answer("Оплата отменена.")


async def cmd_notify(message: types.Message):
    if not message.text.startswith(f"/{NOTIFY_CMD}"):
        return
    await _daily_check(message.bot)
    await message.answer("Уведомления отправлены")


def register(dp: Dispatcher):
    dp.message.register(cmd_success, Command(SUCCESS_CMD))
    dp.message.register(cmd_refused, Command(REFUSED_CMD))
    dp.message.register(cmd_notify, Command(NOTIFY_CMD))
    dp.message.register(show_subscription_menu, F.text == "⚡ Подписка")
    dp.message.register(
        choose_plan,
        F.text.in_(
            {
                "🚶‍♂️1 месяц - 149₽",
                "🏃‍♂️3 месяца - 399₽",
                "🧘‍♂️6 месяцев - 799₽",
            }
        ),
    )
    dp.message.register(
        choose_method,
        SubscriptionState.choosing_method,
    )
    dp.callback_query.register(cb_pay, F.data == "pay")
    dp.callback_query.register(cb_subscribe, F.data == "subscribe")

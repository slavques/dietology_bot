from aiogram import types, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func

from ..database import (
    SessionLocal,
    User,
    Comment,
    EngagementStatus,
    Subscription,
    Payment,
)
from ..states import AdminState
from ..config import ADMIN_COMMAND, ADMIN_PASSWORD
from ..keyboards import subscribe_button
from ..logger import log
from ..messaging import deliver_text, send_with_retries
from ..texts import (
    BTN_BROADCAST,
    BTN_BROADCAST_TEXT,
    BTN_BROADCAST_SUPPORT,
    BTN_SUPPORT,
    BTN_BACK,
    BTN_DAYS,
    BTN_ONE,
    BTN_ALL,
    BTN_DISCOUNT,
    BTN_BLOCK,
    BTN_BLOCKED_USERS,
    BTN_FEATURES,
    BTN_METHODS,
    BTN_GRADES,
    BTN_REFERRAL,
    BTN_BANK_CARD,
    BTN_TELEGRAM_STARS,
    BTN_CRYPTO,
    BTN_SETTINGS,
    BTN_REMINDERS,
    BTN_GOALS,
    BTN_MANUAL,
    BTN_GRADE_START,
    BTN_GRADE_PRO,
    BTN_STATS_ADMIN,
    BTN_YES,
    BTN_NO,
    BTN_PREV,
    BTN_NEXT,
    BTN_TRIAL,
    BTN_TRIAL_START,
    BTN_STATUS,
    BTN_TRIAL_DAYS,
    BTN_GRADE,
    BTN_USER,
    BTN_COMMENT,
    BTN_CONFIRM,
    BTN_REMOVE_LIMITS,
    ADMIN_GRADE_DONE,
    ADMIN_MODE,
    ADMIN_UNAVAILABLE,
    BROADCAST_CHOOSE,
    BROADCAST_PROMPT,
    BROADCAST_ERROR,
    BROADCAST_DONE,
    BROADCAST_SUPPORT_PROMPT,
    ADMIN_CHOOSE_ACTION,
    ADMIN_ENTER_ID,
    ADMIN_ENTER_DAYS,
    ADMIN_DAYS_DONE,
    ADMIN_BLOCK_DONE,
    ADMIN_UNBLOCK_DONE,
    ADMIN_UNBLOCK_CONFIRM,
    ADMIN_USER_NOT_FOUND,
    ADMIN_ENTER_COMMENT,
    ADMIN_BLOCKED_TITLE,
    ADMIN_BLOCKED_EMPTY,
    ADMIN_METHODS_TITLE,
    ADMIN_GRADES_TITLE,
    ADMIN_SETTINGS_TITLE,
    ADMIN_TRIAL_DONE,
    ADMIN_DISCOUNT_PROMPT,
    ADMIN_DISCOUNT_DONE,
    ADMIN_DISCOUNT_COOLDOWN,
    ADMIN_STATS,
    ADMIN_REFERRAL_TITLE,
    ADMIN_REFERRAL_EMPTY,
    DISCOUNT_MESSAGE,
    RETURN_DISCOUNT_MESSAGE,
    format_date_ru,
)
from ..subscriptions import PAID_LIMIT

admins = set()


def grade_title(grade: str) -> str:
    return "PRO" if grade.startswith("pro") else "Старт"


def build_user_info(session: SessionLocal, user: User) -> str:
    from ..subscriptions import days_left

    days = days_left(user)
    frozen = "нет"
    if user.resume_grade:
        d = None
        if user.resume_period_end:
            d = (user.resume_period_end.date() - datetime.utcnow().date()).days
        frozen = grade_title(user.resume_grade)
        if d is not None:
            frozen += f" ({d})"
    comments = (
        session.query(Comment)
        .filter_by(user_id=user.id)
        .order_by(Comment.timestamp.desc())
        .all()
    )
    comments_text = "\n".join(f"{c.timestamp.date()} - {c.text}" for c in comments) or "-"
    if user.grade == "free":
        sub = "бесплатный"
    elif user.trial:
        sub = f"пробный ({grade_title(user.grade)})"
    else:
        sub = f"платный ({grade_title(user.grade)})"
    return (
        f"ID: {user.telegram_id}\n"
        f"Дата старта: {user.created_at.date()}\n"
        f"Текущая подписка: {sub}\n"
        f"Остаток дней по текущей подписке: {days if days is not None else '-'}\n"
        f"Замороженная подписка: {frozen}\n"
        f"Общее кол-во запросов: {user.requests_total}\n"
        f"Кол-во запросов за месяц: {user.monthly_used}\n"
        f"Комментарии:\n{comments_text}"
    )


def admin_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BROADCAST, callback_data="admin:broadcast")
    builder.button(text=BTN_DISCOUNT, callback_data="admin:discount")
    builder.button(text=BTN_DAYS, callback_data="admin:days")
    builder.button(text=BTN_FEATURES, callback_data="admin:features")
    builder.button(text=BTN_TRIAL, callback_data="admin:trial")
    builder.button(text=BTN_GRADE, callback_data="admin:grade")
    builder.button(text=BTN_REFERRAL, callback_data="admin:referral")
    builder.button(text=BTN_BLOCK, callback_data="admin:block")
    builder.button(text=BTN_BLOCKED_USERS, callback_data="admin:blocked")
    builder.button(text=BTN_USER, callback_data="admin:user")
    builder.button(text=BTN_STATS_ADMIN, callback_data="admin:stats")
    builder.adjust(1)
    return builder.as_markup()


def broadcast_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BROADCAST_TEXT, callback_data="admin:broadcast:text")
    builder.button(text=BTN_BROADCAST_SUPPORT, callback_data="admin:broadcast:support")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_back_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


async def admin_referral_list(query: types.CallbackQuery, page: Optional[int] = None):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    session = SessionLocal()
    results = (
        session.query(User.referrer_id, func.count(User.id))
        .filter(User.referrer_id.isnot(None))
        .group_by(User.referrer_id)
        .order_by(func.count(User.id).desc())
        .all()
    )
    per_page = 6
    total = len(results)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page is None:
        parts = query.data.split(":")
        try:
            page = int(parts[2])
        except (IndexError, ValueError):
            page = 0
    if page >= total_pages:
        page = total_pages - 1
    start = page * per_page
    chunk = results[start : start + per_page]
    lines = [f"{tg_id} — ({cnt})" for tg_id, cnt in chunk]
    text = (
        "\n".join(lines) if lines else ADMIN_REFERRAL_EMPTY
    )
    text = f"{ADMIN_REFERRAL_TITLE}\n{text}" if lines else ADMIN_REFERRAL_EMPTY
    builder = InlineKeyboardBuilder()
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(
                types.InlineKeyboardButton(
                    text=BTN_PREV, callback_data=f"admin:referral:{page-1}"
                )
            )
        if page < total_pages - 1:
            nav.append(
                types.InlineKeyboardButton(
                    text=BTN_NEXT, callback_data=f"admin:referral:{page+1}"
                )
            )
    if nav:
        builder.row(*nav)
    builder.row(types.InlineKeyboardButton(text=BTN_BACK, callback_data="admin:menu"))
    await query.message.edit_text(text, reply_markup=builder.as_markup())
    session.close()
    await query.answer()


def days_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_ONE, callback_data="admin:days_one")
    builder.button(text=BTN_ALL, callback_data="admin:days_all")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def discount_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_ALL, callback_data="admin:discount_all")
    builder.button(text=BTN_ONE, callback_data="admin:discount_one")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def discount_confirm_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_CONFIRM, callback_data="admin:discount_confirm")
    builder.button(text=BTN_BACK, callback_data="admin:discount")
    builder.adjust(1)
    return builder.as_markup()


def trial_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_ONE, callback_data="admin:trial_one")
    builder.button(text=BTN_ALL, callback_data="admin:trial_all")
    builder.button(text=BTN_TRIAL_START, callback_data="admin:trial_start")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def trial_grade_kb(prefix: str) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_GRADE_PRO, callback_data=f"admin:{prefix}:pro")
    builder.button(text=BTN_GRADE_START, callback_data=f"admin:{prefix}:light")
    builder.button(text=BTN_BACK, callback_data="admin:trial")
    builder.adjust(1)
    return builder.as_markup()


def grade_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_GRADE_PRO, callback_data="admin:grade_set:pro")
    builder.button(text=BTN_GRADE_START, callback_data="admin:grade_set:light")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def trial_start_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_GRADE_PRO, callback_data="admin:trial_start:pro")
    builder.button(text=BTN_GRADE_START, callback_data="admin:trial_start:light")
    builder.button(text=BTN_BACK, callback_data="admin:trial")
    builder.adjust(1)
    return builder.as_markup()


def trial_start_grade_kb(grade: str) -> types.InlineKeyboardMarkup:
    from ..database import get_option_bool, get_option_int

    builder = InlineKeyboardBuilder()
    status = "🟢" if get_option_bool(f"trial_{grade}_enabled", False) else "🔴"
    days = get_option_int(f"trial_{grade}_days", 0)
    builder.button(text=f"{BTN_STATUS} {status}", callback_data=f"admin:trial_toggle:{grade}")
    builder.button(text=BTN_TRIAL_DAYS.format(days=days), callback_data=f"admin:trial_days_set:{grade}")
    builder.button(text=BTN_BACK, callback_data="admin:trial_start")
    builder.adjust(1)
    return builder.as_markup()


async def admin_login(message: types.Message):
    if not message.text.startswith(f"/{ADMIN_COMMAND}"):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or parts[1] != ADMIN_PASSWORD:
        return
    admins.add(message.from_user.id)
    await message.answer(ADMIN_MODE, reply_markup=admin_menu_kb())


async def admin_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_MODE, reply_markup=admin_menu_kb())
    await query.answer()


async def admin_broadcast_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(BROADCAST_CHOOSE, reply_markup=broadcast_menu_kb())
    await query.answer()


async def admin_broadcast_prompt(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_broadcast)
    await query.message.edit_text(BROADCAST_PROMPT, reply_markup=admin_back_kb())
    await query.answer()


async def admin_broadcast_support_prompt(
    query: types.CallbackQuery, state: FSMContext
):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_broadcast_support)
    await query.message.edit_text(
        BROADCAST_SUPPORT_PROMPT, reply_markup=admin_back_kb()
    )
    await query.answer()


async def admin_discount_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=discount_menu_kb())
    await query.answer()


async def admin_discount_all(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.update_data(discount_target=("all", None))
    await state.set_state(AdminState.waiting_discount_confirm)
    await query.message.edit_text(ADMIN_DISCOUNT_PROMPT, reply_markup=discount_confirm_kb())
    await query.answer()


async def admin_discount_one(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_discount_id)
    await query.message.edit_text(ADMIN_ENTER_ID, reply_markup=admin_back_kb())
    await query.answer()


async def process_discount_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_ID)
        return
    await state.update_data(discount_target=("one", tg_id))
    await state.set_state(AdminState.waiting_discount_confirm)
    await message.answer(ADMIN_DISCOUNT_PROMPT, reply_markup=discount_confirm_kb())


async def admin_discount_confirm(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    data = await state.get_data()
    target, tg_id = data.get("discount_target", (None, None))
    session = SessionLocal()
    now = datetime.utcnow()
    expire = now + timedelta(hours=24)
    text_new = DISCOUNT_MESSAGE.format(
        date=format_date_ru(expire.date()), time=expire.strftime("%H:%M")
    )
    text_return = RETURN_DISCOUNT_MESSAGE.format(
        date=format_date_ru(expire.date()), time=expire.strftime("%H:%M")
    )
    count = 0
    failed: list[int] = []
    sent_stats = {"new": 0, "return": 0}

    def determine_discount_type(
        user: User,
        *,
        respect_cooldown: bool = True,
        skip_inactive: bool = True,
    ) -> Optional[str]:
        subscription = user.subscription
        if not subscription or subscription.grade != "free":
            return None
        if skip_inactive and (user.blocked or user.left_bot):
            return None
        engagement = user.engagement
        if respect_cooldown and engagement and engagement.discount_sent:
            last_sent_at = engagement.discount_last_sent
            if not last_sent_at and engagement.discount_expires:
                last_sent_at = engagement.discount_expires - timedelta(days=1)
            if last_sent_at and last_sent_at > now - timedelta(days=30):
                return None
        last_payment = (
            session.query(Payment)
            .filter_by(user_id=user.id)
            .order_by(Payment.timestamp.desc())
            .first()
        )
        if last_payment is None:
            if user.created_at and user.created_at <= now - timedelta(days=3):
                return "new"
            return None
        if last_payment.timestamp > now - timedelta(days=3):
            return None
        period_end = subscription.period_end
        if not period_end or period_end > now - timedelta(days=3):
            return None
        return "return"

    if target == "all":
        users = (
            session.query(User)
            .join(Subscription)
            .filter(Subscription.grade == "free")
            .all()
        )
        for user in users:
            discount_type = determine_discount_type(user)
            if not discount_type:
                continue
            engagement = user.engagement
            if not engagement:
                engagement = EngagementStatus()
                user.engagement = engagement
            text = text_new if discount_type == "new" else text_return
            success = await send_with_retries(
                query.bot,
                user.telegram_id,
                text=text,
                category="discount",
                parse_mode="HTML",
                reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
            )
            if success:
                engagement.discount_sent = True
                engagement.discount_expires = expire
                engagement.discount_last_sent = now
                count += 1
                sent_stats[discount_type] += 1
            else:
                failed.append(user.telegram_id)
    elif target == "one" and tg_id:
        user = session.query(User).filter_by(telegram_id=int(tg_id)).first()
        if user:
            eng = user.engagement
            if not eng:
                eng = EngagementStatus()
                user.engagement = eng
            last_manual_sent = eng.discount_last_sent or (
                eng.discount_expires - timedelta(days=1)
                if eng.discount_sent and eng.discount_expires
                else None
            )
            if last_manual_sent and last_manual_sent > now - timedelta(days=30):
                session.close()
                await state.clear()
                await query.message.edit_text(
                    ADMIN_DISCOUNT_COOLDOWN, reply_markup=admin_menu_kb()
                )
                await query.answer()
                return
            discount_type = determine_discount_type(
                user, respect_cooldown=False, skip_inactive=False
            )
            if discount_type == "return":
                text = text_return
            else:
                text = text_new
            success = await send_with_retries(
                query.bot,
                user.telegram_id,
                text=text,
                category="discount",
                parse_mode="HTML",
                reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
            )
            if success:
                eng.discount_sent = True
                eng.discount_expires = expire
                eng.discount_last_sent = now
                count += 1
                if discount_type in sent_stats:
                    sent_stats[discount_type] += 1
            else:
                failed.append(user.telegram_id)
    session.commit()
    session.close()
    log(
        "discount",
        "discount target %s: delivered %s (new %s, return %s), failed %s",
        target,
        count,
        sent_stats["new"],
        sent_stats["return"],
        len(failed),
    )
    await state.clear()
    result_text = ADMIN_DISCOUNT_DONE
    if target == "all":
        result_text += (
            f"\nНовые пользователи: {sent_stats['new']}"
            f"\nВозврат: {sent_stats['return']}"
        )
    if failed:
        preview = ", ".join(map(str, failed[:10]))
        result_text += f"\nНе доставлено {len(failed)} пользователям."
        if preview:
            result_text += f"\nIDs: {preview}"
    await query.message.edit_text(result_text, reply_markup=admin_menu_kb())
    await query.answer()


async def admin_days_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=days_menu_kb())
    await query.answer()


async def admin_days_one(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_user_id)
    await query.message.edit_text(ADMIN_ENTER_ID, reply_markup=admin_back_kb())
    await query.answer()


async def admin_days_all(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_days_all)
    await query.message.edit_text(ADMIN_ENTER_DAYS, reply_markup=admin_back_kb())
    await query.answer()


async def admin_block_prompt(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_block_id)
    await query.message.edit_text(ADMIN_ENTER_ID, reply_markup=admin_back_kb())
    await query.answer()


async def admin_user_prompt(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_view_id)
    await query.message.edit_text(ADMIN_ENTER_ID, reply_markup=admin_back_kb())
    await query.answer()


async def admin_stats(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    session = SessionLocal()
    now = datetime.utcnow()
    total = session.query(User).count()
    from ..database import Subscription

    light = (
        session.query(User)
        .join(Subscription)
        .filter(Subscription.grade == "light", Subscription.period_end > now)
        .count()
    )
    pro = (
        session.query(User)
        .join(Subscription)
        .filter(Subscription.grade == "pro", Subscription.period_end > now)
        .count()
    )
    trial_pro = (
        session.query(User)
        .join(Subscription)
        .filter(Subscription.grade == "pro_promo", Subscription.trial_end > now)
        .count()
    )
    trial_light = (
        session.query(User)
        .join(Subscription)
        .filter(Subscription.grade == "light_promo", Subscription.trial_end > now)
        .count()
    )
    used = (
        session.query(User)
        .join(Subscription)
        .filter(Subscription.grade == "free", Subscription.requests_used > 0)
        .count()
    )
    unused = (
        session.query(User)
        .join(Subscription)
        .filter(Subscription.grade == "free", Subscription.requests_used == 0)
        .count()
    )
    left = session.query(User).filter_by(left_bot=True).count()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    q_today = (
        session.query(func.sum(Subscription.daily_used))
        .filter(Subscription.daily_start >= start_today)
        .scalar()
        or 0
    )
    session.close()
    text = ADMIN_STATS.format(
        total=total,
        light=light,
        pro=pro,
        trial_pro=trial_pro,
        trial_light=trial_light,
        used=used,
        unused=unused,
        left=left,
        req_today=q_today,
    )
    try:
        await query.message.edit_text(text, reply_markup=admin_menu_kb())
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await query.answer()


def user_info_kb(tg_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_COMMENT, callback_data=f"admin:comment:{tg_id}")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


async def process_view_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_ID)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    if not user:
        session.close()
        await message.answer(ADMIN_USER_NOT_FOUND, reply_markup=admin_menu_kb())
        await state.clear()
        return
    text = build_user_info(session, user)
    kb = user_info_kb(user.telegram_id)
    await message.answer(text, reply_markup=kb)
    session.close()
    await state.clear()


async def admin_comment_prompt(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    try:
        tg_id = int(query.data.split(":")[2])
    except (IndexError, ValueError):
        await query.answer()
        return
    await state.update_data(comment_id=tg_id, info_msg_id=query.message.message_id)
    await state.set_state(AdminState.waiting_comment_text)
    await query.message.edit_text(ADMIN_ENTER_COMMENT, reply_markup=admin_back_kb())
    await query.answer()


async def process_comment_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    data = await state.get_data()
    tg_id = data.get("comment_id")
    info_msg_id = data.get("info_msg_id")
    text = message.text.strip()
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    if user:
        c = Comment(user_id=user.id, text=text)
        session.add(c)
        session.commit()
    if user:
        updated = build_user_info(session, user)
    else:
        updated = ADMIN_USER_NOT_FOUND
    session.close()
    try:
        await message.bot.edit_message_text(
            updated,
            chat_id=message.chat.id,
            message_id=info_msg_id,
            reply_markup=user_info_kb(tg_id) if user else admin_menu_kb(),
        )
    except Exception:
        await message.answer(updated, reply_markup=user_info_kb(tg_id) if user else admin_menu_kb())
    await state.clear()


async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    text = message.text
    session = SessionLocal()
    users = session.query(User).all()
    user_ids = [u.telegram_id for u in users]
    session.close()
    report = await deliver_text(
        message.bot,
        user_ids,
        text=text,
        category="broadcast",
    )
    log(
        "broadcast",
        "sent broadcast from %s to %s users (failed=%s)",
        message.from_user.id,
        report.delivered,
        len(report.failed),
    )
    response = BROADCAST_DONE
    if report.failed:
        failed_preview = ", ".join(map(str, report.failed[:10]))
        extra = f"\nНе доставлено {len(report.failed)} пользователям."
        if failed_preview:
            extra += f"\nIDs: {failed_preview}"
        response = BROADCAST_ERROR + extra
    await message.answer(response, reply_markup=admin_menu_kb())
    await state.clear()


async def process_broadcast_support(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    text = message.text
    session = SessionLocal()
    users = session.query(User).all()
    user_ids = [u.telegram_id for u in users]
    session.close()
    from ..settings import SUPPORT_HANDLE
    url = f"https://t.me/{SUPPORT_HANDLE.lstrip('@')}"
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_SUPPORT, url=url)
    builder.adjust(1)
    kb = builder.as_markup()
    report = await deliver_text(
        message.bot,
        user_ids,
        text=text,
        category="broadcast",
        reply_markup=kb,
    )
    log(
        "broadcast",
        "sent support broadcast from %s to %s users (failed=%s)",
        message.from_user.id,
        report.delivered,
        len(report.failed),
    )
    response = BROADCAST_DONE
    if report.failed:
        failed_preview = ", ".join(map(str, report.failed[:10]))
        extra = f"\nНе доставлено {len(report.failed)} пользователям."
        if failed_preview:
            extra += f"\nIDs: {failed_preview}"
        response = BROADCAST_ERROR + extra
    await message.answer(response, reply_markup=admin_menu_kb())
    await state.clear()


async def process_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await state.update_data(target_id=message.text.strip())
    await state.set_state(AdminState.waiting_days)
    await message.answer(ADMIN_ENTER_DAYS, reply_markup=admin_back_kb())


async def process_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    data = await state.get_data()
    target = data.get("target_id")
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_DAYS)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=int(target)).first()
    if user and user.grade in {"light", "pro"} and not user.trial:
        from ..subscriptions import add_subscription_days

        try:
            add_subscription_days(session, user, days)
            log("days", "added %s days to %s", days, user.telegram_id)
        except Exception as exc:
            session.rollback()
            log("days", "failed to add %s days to %s: %s", days, user.telegram_id, exc)
            session.close()
            await message.answer(
                f"Не удалось начислить дни пользователю {target}",
                reply_markup=admin_menu_kb(),
            )
            await state.clear()
            return
    session.close()
    await message.answer(ADMIN_DAYS_DONE, reply_markup=admin_menu_kb())
    await state.clear()


async def process_days_all(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_DAYS)
        return
    session = SessionLocal()
    from ..subscriptions import add_subscription_days

    from ..database import Subscription

    users = (
        session.query(User)
        .join(Subscription)
        .filter(Subscription.grade.in_(["light", "pro"]))
        .all()
    )
    failed: list[int] = []
    success = 0
    for u in users:
        try:
            add_subscription_days(session, u, days)
            success += 1
        except Exception as exc:
            session.rollback()
            failed.append(u.telegram_id)
            log("days", "failed to add %s days to %s: %s", days, u.telegram_id, exc)
    log(
        "days",
        "added %s days to %s users (failed=%s)",
        days,
        success,
        len(failed),
    )
    session.close()
    text = ADMIN_DAYS_DONE
    if failed:
        preview = ", ".join(map(str, failed[:10]))
        text += f"\nНе удалось начислить {len(failed)} пользователям."
        if preview:
            text += f"\nIDs: {preview}"
    await message.answer(text, reply_markup=admin_menu_kb())
    await state.clear()


async def process_block(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        target = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_ID)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=target).first()
    if user:
        user.blocked = True
        session.commit()
        from ..logger import log
        log("block", "blocked %s", user.telegram_id)
    session.close()
    await message.answer(ADMIN_BLOCK_DONE, reply_markup=admin_menu_kb())
    await state.clear()


async def admin_trial_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=trial_menu_kb())
    await query.answer()


async def admin_trial_one(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.update_data(trial_mode="one")
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=trial_grade_kb("trial_one"))
    await query.answer()


async def admin_trial_all(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.update_data(trial_mode="all")
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=trial_grade_kb("trial_all"))
    await query.answer()


async def admin_trial_grade(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    try:
        _, action, grade = query.data.split(":", 2)
    except ValueError:
        await query.answer()
        return
    mode = action.split("_")[1]
    await state.update_data(trial_grade=grade, trial_mode=mode)
    await state.set_state(AdminState.waiting_trial_days)
    await query.message.edit_text(ADMIN_ENTER_DAYS, reply_markup=admin_back_kb())
    await query.answer()


async def process_trial_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_DAYS)
        return
    data = await state.get_data()
    grade = data.get("trial_grade")
    mode = data.get("trial_mode")
    if mode == "all":
        session = SessionLocal()
        users = session.query(User).all()
        from ..subscriptions import start_trial
        failed: list[int] = []
        for u in users:
            try:
                start_trial(session, u, days, grade)
            except Exception as exc:
                session.rollback()
                failed.append(u.telegram_id)
                log(
                    "trial",
                    "failed to start %s-day %s trial for %s: %s",
                    days,
                    grade,
                    u.telegram_id,
                    exc,
                )
        delivered = len(users) - len(failed)
        log(
            "trial",
            "started %s-day %s trial for all users: success=%s, failed=%s",
            days,
            grade,
            delivered,
            len(failed),
        )
        session.close()
        text = ADMIN_TRIAL_DONE
        if failed:
            preview = ", ".join(map(str, failed[:10]))
            text += f"\nНе удалось подключить {len(failed)} пользователям."
            if preview:
                text += f"\nIDs: {preview}"
        await message.answer(text, reply_markup=admin_menu_kb())
        await state.clear()
    else:
        await state.update_data(trial_days=days)
        await state.set_state(AdminState.waiting_trial_user_id)
        await message.answer(ADMIN_ENTER_ID, reply_markup=admin_back_kb())


async def process_trial_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    data = await state.get_data()
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_ID)
        return
    days = int(data.get("trial_days", 0))
    grade = data.get("trial_grade")
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user:
        from ..subscriptions import start_trial
        try:
            start_trial(session, user, days, grade)
            log("trial", "started %s-day %s trial for %s", days, grade, telegram_id)
        except Exception as exc:
            session.rollback()
            log(
                "trial",
                "failed to start %s-day %s trial for %s: %s",
                days,
                grade,
                telegram_id,
                exc,
            )
            await message.answer(
                f"Не удалось подключить пробный период для {telegram_id}",
                reply_markup=admin_menu_kb(),
            )
            session.close()
            await state.clear()
            return
    session.close()
    await message.answer(ADMIN_TRIAL_DONE, reply_markup=admin_menu_kb())
    await state.clear()


async def admin_grade_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=grade_menu_kb())
    await query.answer()


async def admin_grade_type(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    grade = query.data.split(":")[2]
    await state.update_data(grade_type=grade)
    await state.set_state(AdminState.waiting_grade_days)
    await query.message.edit_text(ADMIN_ENTER_DAYS, reply_markup=admin_back_kb())
    await query.answer()


async def process_grade_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_DAYS)
        return
    await state.update_data(grade_days=days)
    await state.set_state(AdminState.waiting_grade_user_id)
    await message.answer(ADMIN_ENTER_ID, reply_markup=admin_back_kb())


async def process_grade_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    data = await state.get_data()
    grade = data.get("grade_type")
    days = int(data.get("grade_days", 0))
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_ID)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        from ..subscriptions import ensure_user
        user = ensure_user(session, telegram_id)
    now = datetime.utcnow()
    if user.trial:
        user.trial = False
        user.trial_end = None
        user.resume_grade = None
        user.resume_period_end = None
    user.grade = grade
    user.request_limit = PAID_LIMIT
    user.requests_used = 0
    user.period_start = now
    user.period_end = now + timedelta(days=days)
    user.notified_7d = False
    user.notified_3d = False
    user.notified_1d = False
    user.notified_0d = False
    session.commit()
    from ..logger import log
    log("grade", "set %s grade for %s days to %s", grade, days, telegram_id)
    session.close()
    await message.answer(ADMIN_GRADE_DONE, reply_markup=admin_menu_kb())
    await state.clear()


async def admin_trial_start(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=trial_start_menu_kb())
    await query.answer()


async def admin_trial_start_grade(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    grade = query.data.split(":")[2]
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=trial_start_grade_kb(grade))
    await query.answer()


async def admin_trial_toggle(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    grade = query.data.split(":")[2]
    from ..database import get_option_bool, set_option

    key = f"trial_{grade}_enabled"
    enabled = get_option_bool(key, False)
    set_option(key, "0" if enabled else "1")
    if not enabled:
        # disable the other start mode if enabling this one
        other = "pro" if grade == "light" else "light"
        set_option(f"trial_{other}_enabled", "0")
    from ..logger import log
    log("trial", "%s toggled to %s", key, not enabled)
    await admin_trial_start_grade(query)


async def admin_trial_days_set(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    grade = query.data.split(":")[2]
    await state.update_data(trial_grade=grade)
    await state.set_state(AdminState.waiting_trial_start_days)
    await query.message.edit_text(ADMIN_ENTER_DAYS, reply_markup=admin_back_kb())
    await query.answer()


async def process_trial_start_days(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(ADMIN_ENTER_DAYS)
        return
    data = await state.get_data()
    grade = data.get("trial_grade")
    from ..database import set_option

    set_option(f"trial_{grade}_days", str(days))
    await message.answer(ADMIN_DAYS_DONE, reply_markup=admin_menu_kb())
    await state.clear()


def unblock_confirm_kb(telegram_id: int, page: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=BTN_YES, callback_data=f"admin:unblock_yes:{telegram_id}:{page}"
    )
    builder.button(text=BTN_NO, callback_data=f"admin:blocked:{page}")
    builder.button(text=BTN_PREV, callback_data=f"admin:blocked:{page}")
    builder.adjust(2, 1)
    return builder.as_markup()


async def admin_blocked_list(query: types.CallbackQuery, page: Optional[int] = None):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    session = SessionLocal()
    users = session.query(User).filter_by(blocked=True).order_by(User.telegram_id).all()
    per_page = 6
    total = len(users)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page is None:
        parts = query.data.split(":")
        try:
            page = int(parts[2])
        except (IndexError, ValueError):
            page = 0
    if page >= total_pages:
        page = total_pages - 1
    start = page * per_page
    chunk = users[start : start + per_page]
    builder = InlineKeyboardBuilder()
    for u in chunk:
        builder.button(
            text=str(u.telegram_id), callback_data=f"admin:unblock:{u.telegram_id}:{page}"
        )
    builder.adjust(1)
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(
                types.InlineKeyboardButton(
                    text=BTN_PREV, callback_data=f"admin:blocked:{page-1}"
                )
            )
        if page < total_pages - 1:
            nav.append(
                types.InlineKeyboardButton(
                    text=BTN_NEXT, callback_data=f"admin:blocked:{page+1}"
                )
            )
    if nav:
        builder.row(*nav)
    builder.row(types.InlineKeyboardButton(text=BTN_BACK, callback_data="admin:menu"))
    text = ADMIN_BLOCKED_TITLE if users else ADMIN_BLOCKED_EMPTY
    await query.message.edit_text(text, reply_markup=builder.as_markup())
    session.close()
    await query.answer()


async def admin_unblock_prompt(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    parts = query.data.split(":")
    try:
        telegram_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
    except (IndexError, ValueError):
        await query.answer()
        return
    await query.message.edit_text(
        ADMIN_UNBLOCK_CONFIRM.format(telegram_id=telegram_id),
        reply_markup=unblock_confirm_kb(telegram_id, page),
    )
    await query.answer()


async def admin_unblock(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    parts = query.data.split(":")
    try:
        telegram_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
    except (IndexError, ValueError):
        await query.answer()
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user:
        user.blocked = False
        session.commit()
    from ..logger import log
    log("block", "unblocked %s", telegram_id)
    session.close()
    await query.answer(ADMIN_UNBLOCK_DONE)
    await admin_blocked_list(query, page)


def features_menu_kb() -> types.InlineKeyboardMarkup:
    from ..database import get_option_bool

    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_METHODS, callback_data="admin:methods")
    builder.button(text=BTN_GRADES, callback_data="admin:grades")
    manual = "🟢" if get_option_bool("feat_manual") else "🔴"
    referral = "🟢" if get_option_bool("feat_referral") else "🔴"
    builder.button(text=BTN_SETTINGS, callback_data="admin:settings")
    builder.button(
        text=f"{BTN_MANUAL} {manual}", callback_data="admin:toggle:feat_manual"
    )
    builder.button(
        text=f"{BTN_REFERRAL} {referral}", callback_data="admin:toggle:feat_referral"
    )
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_settings_kb() -> types.InlineKeyboardMarkup:
    from ..database import get_option_bool

    builder = InlineKeyboardBuilder()
    settings = "🟢" if get_option_bool("feat_settings") else "🔴"
    reminders = "🟢" if get_option_bool("feat_reminders") else "🔴"
    goals = "🟢" if get_option_bool("feat_goals") else "🔴"
    builder.button(
        text=f"{BTN_SETTINGS} {settings}", callback_data="admin:toggle:feat_settings"
    )
    builder.button(
        text=f"{BTN_REMINDERS} {reminders}", callback_data="admin:toggle:feat_reminders"
    )
    builder.button(
        text=f"{BTN_GOALS} {goals}", callback_data="admin:toggle:feat_goals"
    )
    builder.button(text=BTN_BACK, callback_data="admin:features")
    builder.adjust(1)
    return builder.as_markup()


def methods_kb() -> types.InlineKeyboardMarkup:
    from ..database import get_option_bool

    builder = InlineKeyboardBuilder()
    bank = "🟢" if get_option_bool("pay_card") else "🔴"
    stars = "🟢" if get_option_bool("pay_stars") else "🔴"
    crypto = "🟢" if get_option_bool("pay_crypto") else "🔴"
    builder.button(text=f"{BTN_BANK_CARD} {bank}", callback_data="admin:toggle:pay_card")
    builder.button(text=f"{BTN_TELEGRAM_STARS} {stars}", callback_data="admin:toggle:pay_stars")
    builder.button(text=f"{BTN_CRYPTO} {crypto}", callback_data="admin:toggle:pay_crypto")
    builder.button(text=BTN_BACK, callback_data="admin:features")
    builder.adjust(1)
    return builder.as_markup()


def grades_kb() -> types.InlineKeyboardMarkup:
    from ..database import get_option_bool

    builder = InlineKeyboardBuilder()
    light = "🟢" if get_option_bool("grade_light") else "🔴"
    pro = "🟢" if get_option_bool("grade_pro") else "🔴"
    builder.button(text=f"{BTN_GRADE_PRO} {pro}", callback_data="admin:toggle:grade_pro")
    builder.button(text=f"{BTN_GRADE_START} {light}", callback_data="admin:toggle:grade_light")
    builder.button(text=BTN_BACK, callback_data="admin:features")
    builder.adjust(1)
    return builder.as_markup()


async def admin_features(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_CHOOSE_ACTION, reply_markup=features_menu_kb())
    await query.answer()


async def admin_methods(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_METHODS_TITLE, reply_markup=methods_kb())
    await query.answer()


async def admin_grades(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_GRADES_TITLE, reply_markup=grades_kb())
    await query.answer()


async def admin_settings_menu(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await query.message.edit_text(ADMIN_SETTINGS_TITLE, reply_markup=admin_settings_kb())
    await query.answer()


async def admin_toggle(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    try:
        key = query.data.split(":", 2)[2]
    except IndexError:
        await query.answer()
        return
    from ..database import get_option_bool, set_option

    enabled = get_option_bool(key)
    set_option(key, "0" if enabled else "1")
    from ..logger import log
    log("feature", "%s set to %s", key, not enabled)
    if key.startswith("pay_"):
        await admin_methods(query)
    elif key.startswith("grade_"):
        await admin_grades(query)
    else:
        await admin_features(query)


def register(dp: Dispatcher):
    dp.message.register(admin_login, F.text.startswith(f"/{ADMIN_COMMAND}"))
    dp.callback_query.register(admin_broadcast_menu, F.data == "admin:broadcast")
    dp.callback_query.register(admin_broadcast_prompt, F.data == "admin:broadcast:text")
    dp.callback_query.register(
        admin_broadcast_support_prompt, F.data == "admin:broadcast:support"
    )
    dp.callback_query.register(admin_discount_menu, F.data == "admin:discount")
    dp.callback_query.register(admin_discount_all, F.data == "admin:discount_all")
    dp.callback_query.register(admin_discount_one, F.data == "admin:discount_one")
    dp.callback_query.register(admin_discount_confirm, F.data == "admin:discount_confirm")
    dp.callback_query.register(admin_days_menu, F.data == "admin:days")
    dp.callback_query.register(admin_days_one, F.data == "admin:days_one")
    dp.callback_query.register(admin_days_all, F.data == "admin:days_all")
    dp.callback_query.register(admin_block_prompt, F.data == "admin:block")
    dp.callback_query.register(admin_user_prompt, F.data == "admin:user")
    dp.callback_query.register(admin_comment_prompt, F.data.startswith("admin:comment:"))
    dp.callback_query.register(admin_trial_menu, F.data == "admin:trial")
    dp.callback_query.register(admin_trial_one, F.data == "admin:trial_one")
    dp.callback_query.register(admin_trial_all, F.data == "admin:trial_all")
    dp.callback_query.register(admin_trial_grade, F.data.startswith("admin:trial_one"))
    dp.callback_query.register(admin_trial_grade, F.data.startswith("admin:trial_all"))
    dp.callback_query.register(admin_trial_start, F.data == "admin:trial_start")
    dp.callback_query.register(admin_trial_start_grade, F.data.startswith("admin:trial_start:"))
    dp.callback_query.register(admin_trial_toggle, F.data.startswith("admin:trial_toggle:"))
    dp.callback_query.register(admin_trial_days_set, F.data.startswith("admin:trial_days_set:"))
    dp.callback_query.register(admin_features, F.data == "admin:features")
    dp.callback_query.register(admin_methods, F.data == "admin:methods")
    dp.callback_query.register(admin_grades, F.data == "admin:grades")
    dp.callback_query.register(admin_settings_menu, F.data == "admin:settings")
    dp.callback_query.register(admin_toggle, F.data.startswith("admin:toggle:"))
    dp.callback_query.register(admin_grade_menu, F.data == "admin:grade")
    dp.callback_query.register(admin_grade_type, F.data.startswith("admin:grade_set:"))
    dp.callback_query.register(admin_blocked_list, F.data.startswith("admin:blocked"))
    dp.callback_query.register(admin_unblock_prompt, F.data.startswith("admin:unblock:"))
    dp.callback_query.register(admin_unblock, F.data.startswith("admin:unblock_yes:"))
    dp.callback_query.register(admin_stats, F.data == "admin:stats")
    dp.callback_query.register(admin_referral_list, F.data.startswith("admin:referral"))
    dp.callback_query.register(admin_menu, F.data == "admin:menu")
    dp.message.register(process_broadcast, AdminState.waiting_broadcast, F.text)
    dp.message.register(process_broadcast_support, AdminState.waiting_broadcast_support, F.text)
    dp.message.register(process_user_id, AdminState.waiting_user_id, F.text)
    dp.message.register(process_days, AdminState.waiting_days, F.text)
    dp.message.register(process_days_all, AdminState.waiting_days_all, F.text)
    dp.message.register(process_block, AdminState.waiting_block_id, F.text)
    dp.message.register(process_trial_days, AdminState.waiting_trial_days, F.text)
    dp.message.register(process_trial_user_id, AdminState.waiting_trial_user_id, F.text)
    dp.message.register(process_trial_start_days, AdminState.waiting_trial_start_days, F.text)
    dp.message.register(process_grade_days, AdminState.waiting_grade_days, F.text)
    dp.message.register(process_grade_user_id, AdminState.waiting_grade_user_id, F.text)
    dp.message.register(process_view_id, AdminState.waiting_view_id, F.text)
    dp.message.register(process_comment_text, AdminState.waiting_comment_text, F.text)
    dp.message.register(process_discount_user_id, AdminState.waiting_discount_id, F.text)

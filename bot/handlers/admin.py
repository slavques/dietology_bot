from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from ..database import SessionLocal, User
from ..states import AdminState
from ..config import ADMIN_COMMAND, ADMIN_PASSWORD
from ..texts import (
    BTN_BROADCAST,
    BTN_BACK,
    BTN_DAYS,
    BTN_ONE,
    BTN_ALL,
    BTN_BLOCK,
    BTN_BLOCKED_USERS,
    BTN_FEATURES,
    BTN_METHODS,
    BTN_GRADES,
    BTN_BANK_CARD,
    BTN_TELEGRAM_STARS,
    BTN_CRYPTO,
    BTN_SETTINGS,
    BTN_MANUAL,
    BTN_GRADE_START,
    BTN_GRADE_PRO,
    BTN_STATS_ADMIN,
    BTN_TRIAL,
    BTN_TRIAL_START,
    BTN_STATUS,
    BTN_TRIAL_DAYS,
    ADMIN_MODE,
    ADMIN_UNAVAILABLE,
    BROADCAST_PROMPT,
    BROADCAST_ERROR,
    BROADCAST_DONE,
    ADMIN_CHOOSE_ACTION,
    ADMIN_ENTER_ID,
    ADMIN_ENTER_DAYS,
    ADMIN_DAYS_DONE,
    ADMIN_BLOCK_DONE,
    ADMIN_UNBLOCK_DONE,
    ADMIN_BLOCKED_TITLE,
    ADMIN_BLOCKED_EMPTY,
    ADMIN_METHODS_TITLE,
    ADMIN_GRADES_TITLE,
    ADMIN_TRIAL_DONE,
    ADMIN_STATS,
)

admins = set()


def admin_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BROADCAST, callback_data="admin:broadcast")
    builder.button(text=BTN_DAYS, callback_data="admin:days")
    builder.button(text=BTN_FEATURES, callback_data="admin:features")
    builder.button(text=BTN_TRIAL, callback_data="admin:trial")
    builder.button(text=BTN_BLOCK, callback_data="admin:block")
    builder.button(text=BTN_BLOCKED_USERS, callback_data="admin:blocked")
    builder.button(text=BTN_STATS_ADMIN, callback_data="admin:stats")
    builder.adjust(1)
    return builder.as_markup()


def admin_back_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def days_menu_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_ONE, callback_data="admin:days_one")
    builder.button(text=BTN_ALL, callback_data="admin:days_all")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
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


async def admin_broadcast_prompt(query: types.CallbackQuery, state: FSMContext):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    await state.set_state(AdminState.waiting_broadcast)
    await query.message.edit_text(BROADCAST_PROMPT, reply_markup=admin_back_kb())
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


async def admin_stats(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    session = SessionLocal()
    now = datetime.utcnow()
    total = session.query(User).count()
    paid = session.query(User).filter(User.grade == "light", User.period_end > now).count()
    pro = session.query(User).filter(User.grade == "pro", User.period_end > now).count()
    used = session.query(User).filter(User.grade == "free", User.requests_used > 0).count()
    session.close()
    text = ADMIN_STATS.format(total=total, paid=paid, pro=pro, used=used)
    await query.message.edit_text(text, reply_markup=admin_menu_kb())
    await query.answer()


async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    text = message.text
    session = SessionLocal()
    users = session.query(User).all()
    error = False
    for u in users:
        try:
            await message.bot.send_message(u.telegram_id, text)
        except Exception:
            error = True
    session.close()
    from ..logger import log
    log("broadcast", "sent broadcast from %s to %s users", message.from_user.id, len(users))
    await message.answer(
        BROADCAST_ERROR if error else BROADCAST_DONE,
        reply_markup=admin_menu_kb(),
    )
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

        add_subscription_days(session, user, days)
        from ..logger import log
        log("days", "added %s days to %s", days, user.telegram_id)
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

    users = (
        session.query(User)
        .filter(User.grade.in_(["light", "pro"]))
        .all()
    )
    for u in users:
        add_subscription_days(session, u, days)
    from ..logger import log
    log("days", "added %s days to all %s users", days, len(users))
    session.close()
    await message.answer(ADMIN_DAYS_DONE, reply_markup=admin_menu_kb())
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
        for u in users:
            start_trial(session, u, days, grade)
        from ..logger import log
        log("trial", "started %s-day %s trial for all %s users", days, grade, len(users))
        session.close()
        await message.answer(ADMIN_TRIAL_DONE, reply_markup=admin_menu_kb())
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
        start_trial(session, user, days, grade)
        from ..logger import log
        log("trial", "started %s-day %s trial for %s", days, grade, telegram_id)
    session.close()
    await message.answer(ADMIN_TRIAL_DONE, reply_markup=admin_menu_kb())
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


async def admin_blocked_list(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    session = SessionLocal()
    users = session.query(User).filter_by(blocked=True).all()
    builder = InlineKeyboardBuilder()
    for u in users:
        builder.button(text=str(u.telegram_id), callback_data=f"admin:unblock:{u.telegram_id}")
    builder.button(text=BTN_BACK, callback_data="admin:menu")
    builder.adjust(1)
    text = ADMIN_BLOCKED_TITLE if users else ADMIN_BLOCKED_EMPTY
    await query.message.edit_text(text, reply_markup=builder.as_markup())
    session.close()
    await query.answer()


async def admin_unblock(query: types.CallbackQuery):
    if query.from_user.id not in admins:
        await query.answer(ADMIN_UNAVAILABLE, show_alert=True)
        return
    try:
        telegram_id = int(query.data.split(":")[2])
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
    await admin_blocked_list(query)


def features_menu_kb() -> types.InlineKeyboardMarkup:
    from ..database import get_option_bool

    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_METHODS, callback_data="admin:methods")
    builder.button(text=BTN_GRADES, callback_data="admin:grades")
    settings = "🟢" if get_option_bool("feat_settings") else "🔴"
    manual = "🟢" if get_option_bool("feat_manual") else "🔴"
    builder.button(
        text=f"{BTN_SETTINGS} {settings}", callback_data="admin:toggle:feat_settings"
    )
    builder.button(
        text=f"{BTN_MANUAL} {manual}", callback_data="admin:toggle:feat_manual"
    )
    builder.button(text=BTN_BACK, callback_data="admin:menu")
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
    dp.callback_query.register(admin_broadcast_prompt, F.data == "admin:broadcast")
    dp.callback_query.register(admin_days_menu, F.data == "admin:days")
    dp.callback_query.register(admin_days_one, F.data == "admin:days_one")
    dp.callback_query.register(admin_days_all, F.data == "admin:days_all")
    dp.callback_query.register(admin_block_prompt, F.data == "admin:block")
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
    dp.callback_query.register(admin_toggle, F.data.startswith("admin:toggle:"))
    dp.callback_query.register(admin_blocked_list, F.data == "admin:blocked")
    dp.callback_query.register(admin_unblock, F.data.startswith("admin:unblock:"))
    dp.callback_query.register(admin_stats, F.data == "admin:stats")
    dp.callback_query.register(admin_menu, F.data == "admin:menu")
    dp.message.register(process_broadcast, AdminState.waiting_broadcast, F.text)
    dp.message.register(process_user_id, AdminState.waiting_user_id, F.text)
    dp.message.register(process_days, AdminState.waiting_days, F.text)
    dp.message.register(process_days_all, AdminState.waiting_days_all, F.text)
    dp.message.register(process_block, AdminState.waiting_block_id, F.text)
    dp.message.register(process_trial_days, AdminState.waiting_trial_days, F.text)
    dp.message.register(process_trial_user_id, AdminState.waiting_trial_user_id, F.text)
    dp.message.register(process_trial_start_days, AdminState.waiting_trial_start_days, F.text)

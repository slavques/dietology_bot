import logging
import imghdr
from io import BytesIO

from aiogram import types, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from PIL import Image, UnidentifiedImageError

from ..database import SessionLocal, Goal, Meal, get_option_bool
from ..subscriptions import ensure_user, update_limits
from ..keyboards import (
    goal_start_kb,
    goal_gender_kb,
    goal_back_kb,
    goal_body_fat_kb,
    goal_activity_kb,
    goal_training_kb,
    goal_target_kb,
    goal_plan_kb,
    goal_confirm_kb,
    goals_main_kb,
    goal_edit_kb,
    goal_trends_kb,
    goal_reminders_kb,
    goal_reminders_settings_kb,
    goal_stop_confirm_kb,
    main_menu_kb,
    back_to_goal_reminders_kb,
    back_to_goal_reminders_settings_kb,
    goal_trial_paywall_kb,
    subscribe_button,
)
from ..states import GoalState, GoalReminderState
from ..texts import (
    GOAL_INTRO_TEXT,
    GOAL_FREE_TRIAL_NOTE,
    GOAL_CHOOSE_GENDER,
    GOAL_ENTER_AGE,
    GOAL_ENTER_HEIGHT,
    GOAL_ENTER_WEIGHT,
    GOAL_CHOOSE_BODY_FAT,
    GOAL_CHOOSE_ACTIVITY,
    GOAL_CHOOSE_TRAINING,
    GOAL_CHOOSE_TARGET,
    GOAL_CHOOSE_LOSS_PLAN,
    GOAL_CHOOSE_GAIN_PLAN,
    GOAL_CALC_PROGRESS,
    GOAL_RESULT,
    GOAL_CURRENT,
    GOAL_EDIT_PROMPT,
    GOAL_TRENDS,
    GOAL_REMINDERS_TEXT,
    TZ_PROMPT,
    GOAL_STOP_PROMPT,
    GOAL_STOP_DONE,
    INPUT_NUMBER_PROMPT,
    INPUT_RANGE_ERROR,
    FEATURE_DISABLED,
    INVALID_TIME,
    TIME_CURRENT,
    SET_TIME_PROMPT,
    BTN_MORNING,
    BTN_EVENING,
    BTN_REMOVE_LIMITS,
    GOAL_TRIAL_EXPIRED_NOTICE,
    GOAL_TRIAL_PAYWALL_TEXT,
)
from ..settings import STATIC_DIR, GOAL_BODY_FAT_IMAGE_NAME


logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import object_session


BODY_FAT_IMAGE_MAX_BYTES = 10 * 1024 * 1024


def _goal_body_fat_image_path() -> Optional[Path]:
    if not GOAL_BODY_FAT_IMAGE_NAME:
        return None
    image_path = STATIC_DIR / GOAL_BODY_FAT_IMAGE_NAME
    if not image_path.is_file():
        return None
    return image_path


async def _delete_message_safely(bot, chat_id: int, message_id: Optional[int]) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        pass


def _load_goal_body_fat_photo() -> Optional[Tuple[BufferedInputFile, Path]]:
    image_path = _goal_body_fat_image_path()
    if not image_path:
        logger.debug("Goal body fat illustration is not configured")
        return None
    try:
        file_size = image_path.stat().st_size
    except OSError as err:
        logger.warning("Failed to stat body fat illustration %s: %s", image_path, err)
        return None
    if file_size <= 0:
        logger.warning("Body fat illustration %s is empty", image_path)
        return None
    if file_size > BODY_FAT_IMAGE_MAX_BYTES:
        logger.warning(
            "Body fat illustration %s is too large for Telegram (%s bytes)",
            image_path,
            file_size,
        )
        return None
    try:
        payload = image_path.read_bytes()
    except OSError as err:
        logger.warning("Failed to read body fat illustration %s: %s", image_path, err)
        return None
    image_format = imghdr.what(None, payload)
    supported_formats = {"jpeg", "png"}
    pil_format = ""
    if image_format not in supported_formats:
        try:
            with Image.open(image_path) as illustration:
                pil_format = (illustration.format or "").lower()
                if pil_format in supported_formats:
                    image_format = pil_format
                elif pil_format:
                    buffer = BytesIO()
                    illustration.convert("RGB").save(buffer, format="JPEG")
                    payload = buffer.getvalue()
                    image_format = "jpeg"
        except (UnidentifiedImageError, OSError) as err:
            logger.debug(
                "Pillow could not identify body fat illustration %s: %s", image_path, err
            )
    if image_format not in supported_formats:
        if not image_format:
            extension = image_path.suffix.lower()
            if extension in {".jpg", ".jpeg"}:
                image_format = "jpeg"
            elif extension == ".png":
                image_format = "png"
        if image_format not in supported_formats:
            logger.warning(
                "Body fat illustration %s has unsupported format %s",
                image_path,
                pil_format or image_format or "unknown",
            )
            return None
    filename = image_path.name
    if "." not in filename:
        extension = "jpg" if image_format == "jpeg" else "png"
        filename = f"{filename}.{extension}"
    elif image_format == "jpeg" and not filename.lower().endswith((".jpg", ".jpeg")):
        filename = f"{image_path.stem}.jpg"
    elif image_format == "png" and not filename.lower().endswith(".png"):
        filename = f"{image_path.stem}.png"
    return BufferedInputFile(payload, filename=filename), image_path


async def _show_goal_body_fat_prompt(bot, chat_id: int, state: FSMContext, msg_id: Optional[int]):
    body_fat_photo = _load_goal_body_fat_photo()
    markup = goal_body_fat_kb()
    fallback_msg_id = msg_id
    if body_fat_photo:
        if msg_id:
            await _delete_message_safely(bot, chat_id, msg_id)
            fallback_msg_id = None
        try:
            sent = await bot.send_photo(
                chat_id,
                body_fat_photo[0],
                caption=GOAL_CHOOSE_BODY_FAT,
                reply_markup=markup,
            )
        except TelegramBadRequest as err:
            logger.warning(
                "Failed to send goal body fat illustration, falling back to text prompt: %s",
                err,
            )
            logger.debug("Illustration attempted from %s", body_fat_photo[1])
        else:
            await state.update_data(msg_id=sent.message_id)
            return
    if fallback_msg_id:
        try:
            await bot.edit_message_text(
                GOAL_CHOOSE_BODY_FAT,
                chat_id=chat_id,
                message_id=fallback_msg_id,
                reply_markup=markup,
            )
        except TelegramBadRequest as err:
            logger.warning(
                "Failed to edit body fat prompt message, sending a new one: %s",
                err,
            )
        else:
            await state.update_data(msg_id=fallback_msg_id)
            return
    sent = await bot.send_message(
        chat_id,
        GOAL_CHOOSE_BODY_FAT,
        reply_markup=markup,
    )
    await state.update_data(msg_id=sent.message_id)


def calculate_goal(data: dict) -> tuple[int, int, int, int]:
    gender = data.get("gender", "male")
    age = int(data.get("age", 0))
    height = int(data.get("height", 0))
    weight = max(float(data.get("weight", 0)), 1)
    body_fat = data.get("body_fat")
    activity = data.get("activity")
    work_intensity = data.get("work_intensity")
    training_level = data.get("training_level")
    target = data.get("target", "maintain")
    plan = data.get("plan")

    if body_fat is not None:
        lbm = weight * (1 - float(body_fat) / 100)
        bmr = 370 + 21.6 * lbm
    else:
        lbm = None
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

    if (not work_intensity or not training_level) and isinstance(activity, str):
        if "|" in activity:
            work_part, train_part = activity.split("|", 1)
            work_intensity = work_intensity or work_part
            training_level = training_level or train_part
        else:
            legacy_map = {
                "sedentary": ("study", "none"),
                "low": ("remote", "few"),
                "med": ("office", "some"),
                "high": ("physical", "often"),
                "very_high": ("very_active", "daily"),
            }
            legacy_work, legacy_train = legacy_map.get(activity, ("study", "none"))
            work_intensity = work_intensity or legacy_work
            training_level = training_level or legacy_train

    work_intensity = work_intensity or "study"
    training_level = training_level or "none"

    work_factors = {
        "study": 1.2,
        "remote": 1.28,
        "office": 1.38,
        "physical": 1.55,
        "very_active": 1.75,
    }
    training_bonus = {
        "none": 0.0,
        "few": 0.07,
        "some": 0.14,
        "often": 0.22,
        "daily": 0.30,
    }
    activity_multiplier = work_factors.get(work_intensity, 1.3)
    activity_multiplier *= 1 + training_bonus.get(training_level, 0.0)
    activity_multiplier = min(max(activity_multiplier, 1.1), 2.2)
    maintenance = bmr * activity_multiplier

    if target == "loss":
        if plan == "fast":
            delta = -0.25
        elif plan == "protein":
            delta = -0.17
        else:
            delta = -0.20
    elif target == "gain":
        if plan == "fast":
            delta = 0.18
        elif plan == "protein_carb":
            delta = 0.14
        else:
            delta = 0.12
    else:
        delta = 0.0

    calories = maintenance * (1 + delta)
    min_floor = max(1200 if gender == "female" else 1400, bmr * 1.1)
    max_cap = min(maintenance + 800, 4500)
    if target == "gain":
        min_floor = max(min_floor, maintenance * 0.95)
    calories = max(min_floor, calories)
    calories = min(max_cap, calories)

    if body_fat is not None:
        base_mass = max(lbm, 1)
        if target == "loss":
            protein_per_kg = 2.0
        elif target == "gain":
            protein_per_kg = 1.9 if plan == "protein_carb" else 1.7
        else:
            protein_per_kg = 1.8
    else:
        base_mass = weight
        if target == "loss":
            protein_per_kg = 1.8
        elif target == "gain":
            protein_per_kg = 1.7
        else:
            protein_per_kg = 1.6
    if target == "loss" and plan == "protein":
        protein_per_kg += 0.1
    protein_g = max(base_mass * protein_per_kg, 60)
    max_protein = max(weight * 2.4, protein_g)
    protein_g = min(protein_g, max_protein)

    if target == "loss":
        fat_per_kg = 0.8 if plan != "fast" else 0.7
    elif target == "gain":
        fat_per_kg = 1.0 if plan != "protein_carb" else 0.9
    else:
        fat_per_kg = 0.9
    fat_g = max(fat_per_kg * weight, 40)
    min_fat = max(0.6 * weight, 35)

    protein_cal = protein_g * 4
    fat_cal = fat_g * 9
    remaining_cal = calories - (protein_cal + fat_cal)

    if remaining_cal < 0 and fat_g > min_fat:
        fat_g = min_fat
        fat_cal = fat_g * 9
        remaining_cal = calories - (protein_cal + fat_cal)

    min_protein = max((1.6 if body_fat is not None else 1.4) * base_mass, 55)
    if remaining_cal < 0 and protein_g > min_protein:
        protein_g = min_protein
        protein_cal = protein_g * 4
        remaining_cal = calories - (protein_cal + fat_cal)

    carbs_g = max(remaining_cal / 4, 0)
    if remaining_cal >= 160 and carbs_g < 40:
        carbs_g = 40

    calories = int(round(calories))
    protein = int(round(protein_g))
    fat = int(round(fat_g))
    carbs = int(round(carbs_g))
    return calories, protein, fat, carbs


def goal_summary_text(goal: Goal, session=None) -> str:
    eaten = p_eaten = f_eaten = c_eaten = 0
    if goal and goal.user_id:
        close_session = False
        if session is None:
            session = object_session(goal)
        if session is None:
            session = SessionLocal()
            close_session = True
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        totals = session.query(
            func.coalesce(func.sum(Meal.calories), 0),
            func.coalesce(func.sum(Meal.protein), 0),
            func.coalesce(func.sum(Meal.fat), 0),
            func.coalesce(func.sum(Meal.carbs), 0),
        ).filter(
            Meal.user_id == goal.user_id,
            Meal.timestamp >= start,
            Meal.timestamp < end,
        ).one()
        eaten, p_eaten, f_eaten, c_eaten = [round(value, 1) for value in totals]
        if close_session:
            session.close()
    return GOAL_CURRENT.format(
        cal=goal.calories or 0,
        p=goal.protein or 0,
        f=goal.fat or 0,
        c=goal.carbs or 0,
        eaten=eaten,
        p_eaten=p_eaten,
        f_eaten=f_eaten,
        c_eaten=c_eaten,
    )


def goal_progress_text(goal: Goal, totals: dict) -> str:
    """Return dynamic progress card text after saving a meal."""
    cal = int(totals.get("calories", 0))
    p = int(totals.get("protein", 0))
    f = int(totals.get("fat", 0))
    c = int(totals.get("carbs", 0))
    remain = (goal.calories or 0) - cal
    lines = [
        "📊 Текущий прогресс",
        f"Ккал: {cal} / {goal.calories or 0} (осталось {remain})",
    ]
    pct = lambda val, goal_val: int(val / goal_val * 100) if goal_val else 0
    lines.append(
        f"Б: {pct(p, goal.protein)}% • Ж: {pct(f, goal.fat)}% • У: {pct(c, goal.carbs)}%"
    )
    if goal.calories:
        ratio = cal / goal.calories
        if ratio > 1.10:
            lines.append(f"Превышение на {cal - goal.calories} ккал")
        elif ratio < 0.90:
            lines.append(
                "До цели {dc} ккал и {dp} б, {df} ж, {du} у".format(
                    dc=goal.calories - cal,
                    dp=max(0, goal.protein - p),
                    df=max(0, goal.fat - f),
                    du=max(0, goal.carbs - c),
                )
            )
    return "\n".join(lines)


def goal_trends_report(user, days: int, session) -> str:
    """Return trend statistics for the given user over ``days`` days."""
    goal = getattr(user, "goal", None)
    if not goal:
        base = GOAL_TRENDS.format(
            days=days, balance=0, p=0, p_goal=0, f=0, f_goal=0, c=0, c_goal=0
        )
        return base.rstrip("\n") + "\nПродолжай! 💪"
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start -= timedelta(days=days - 1)
    end = start + timedelta(days=days)
    totals = session.query(
        func.coalesce(func.sum(Meal.calories), 0),
        func.coalesce(func.sum(Meal.protein), 0),
        func.coalesce(func.sum(Meal.fat), 0),
        func.coalesce(func.sum(Meal.carbs), 0),
        func.count(func.distinct(func.date(Meal.timestamp))),
    ).filter(
        Meal.user_id == user.id,
        Meal.timestamp >= start,
        Meal.timestamp < end,
    ).one()
    total_cal, total_p, total_f, total_c, day_count = totals
    denom = day_count or 1
    avg_cal = total_cal / denom
    avg_p = total_p / denom
    avg_f = total_f / denom
    avg_c = total_c / denom
    balance = int(round(avg_cal - (goal.calories or 0)))
    base = GOAL_TRENDS.format(
        days=days,
        balance=balance,
        p=int(avg_p),
        p_goal=int(goal.protein or 0),
        f=int(avg_f),
        f_goal=int(goal.fat or 0),
        c=int(avg_c),
        c_goal=int(goal.carbs or 0),
    )
    return base.rstrip("\n") + "\nПродолжай! 💪"


async def open_goals(query: types.CallbackQuery, state: FSMContext):
    if not get_option_bool("feat_goals"):
        await query.answer(FEATURE_DISABLED, show_alert=True)
        return
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    update_limits(user)
    session.commit()
    now = datetime.utcnow()
    show_trial_note = False

    if user.grade != "free":
        if user.goal_trial_start or user.goal_trial_notified:
            user.goal_trial_start = None
            user.goal_trial_notified = False
            session.commit()
    else:
        start = user.goal_trial_start
        if start and now >= start + timedelta(days=3):
            goal = user.goal
            if goal:
                session.delete(goal)
            if not user.goal_trial_notified:
                await query.message.answer(
                    GOAL_TRIAL_EXPIRED_NOTICE,
                    reply_markup=subscribe_button(BTN_REMOVE_LIMITS),
                )
            user.goal_trial_notified = True
            session.commit()
            await query.message.edit_text(
                GOAL_TRIAL_PAYWALL_TEXT,
                reply_markup=goal_trial_paywall_kb(),
            )
            session.close()
            await query.answer()
            return
        if start is None:
            user.goal_trial_start = now
            user.goal_trial_notified = False
            show_trial_note = True
            session.commit()

    goal = user.goal
    if not goal or not goal.calories:
        intro_text = GOAL_INTRO_TEXT
        if show_trial_note:
            intro_text = f"{GOAL_INTRO_TEXT}\n\n{GOAL_FREE_TRIAL_NOTE}"
        await query.message.edit_text(intro_text, reply_markup=goal_start_kb())
    else:
        await query.message.edit_text(
            goal_summary_text(goal, session), reply_markup=goals_main_kb()
        )
    session.close()
    await query.answer()


async def goal_start(query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(GOAL_CHOOSE_GENDER, reply_markup=goal_gender_kb())
    await state.set_state(GoalState.gender)
    await query.answer()


async def goal_cancel(query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(GOAL_INTRO_TEXT, reply_markup=goal_start_kb())
    await query.answer()


async def goal_set_gender(query: types.CallbackQuery, state: FSMContext):
    value = query.data.split(":")[1]
    await query.message.edit_text(GOAL_ENTER_AGE, reply_markup=goal_back_kb("gender"))
    await state.update_data(gender=value, msg_id=query.message.message_id)
    await state.set_state(GoalState.age)
    await query.answer()


async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
    except ValueError:
        await message.answer(INPUT_NUMBER_PROMPT)
        return
    if not 14 <= age <= 100:
        await message.answer(INPUT_RANGE_ERROR)
        return
    data = await state.get_data()
    msg_id = data.get("msg_id")
    await state.update_data(age=age)
    await message.delete()
    if msg_id:
        await message.bot.edit_message_text(
            GOAL_ENTER_HEIGHT,
            chat_id=message.chat.id,
            message_id=msg_id,
            reply_markup=goal_back_kb("age"),
        )
    else:
        response = await message.answer(
            GOAL_ENTER_HEIGHT, reply_markup=goal_back_kb("age")
        )
        await state.update_data(msg_id=response.message_id)
    await state.set_state(GoalState.height)


async def process_height(message: types.Message, state: FSMContext):
    try:
        height = int(message.text)
    except ValueError:
        await message.answer(INPUT_NUMBER_PROMPT)
        return
    if not 120 <= height <= 230:
        await message.answer(INPUT_RANGE_ERROR)
        return
    data = await state.get_data()
    msg_id = data.get("msg_id")
    await state.update_data(height=height)
    await message.delete()
    if msg_id:
        await message.bot.edit_message_text(
            GOAL_ENTER_WEIGHT,
            chat_id=message.chat.id,
            message_id=msg_id,
            reply_markup=goal_back_kb("height"),
        )
    else:
        response = await message.answer(
            GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("height")
        )
        await state.update_data(msg_id=response.message_id)
    await state.set_state(GoalState.weight)


async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(INPUT_NUMBER_PROMPT)
        return
    if not 35 <= weight <= 300:
        await message.answer(INPUT_RANGE_ERROR)
        return
    data = await state.get_data()
    msg_id = data.get("msg_id")
    await state.update_data(weight=weight)
    await message.delete()
    if data.get("editing"):
        session = SessionLocal()
        user = ensure_user(session, message.from_user.id)
        if not user.goal:
            user.goal = Goal()
        user.goal.weight = weight
        session.commit()
        session.close()
        await state.clear()
        if msg_id:
            await message.bot.edit_message_text(
                GOAL_EDIT_PROMPT,
                chat_id=message.chat.id,
                message_id=msg_id,
                reply_markup=goal_edit_kb(),
            )
        else:
            await message.answer(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
    else:
        await _show_goal_body_fat_prompt(
            message.bot,
            message.chat.id,
            state,
            msg_id,
        )
        await state.set_state(GoalState.body_fat)


async def goal_set_body_fat(query: types.CallbackQuery, state: FSMContext):
    value = query.data.split(":")[1]
    if value != "unknown":
        await state.update_data(body_fat=int(value))
    else:
        await state.update_data(body_fat=None)
    data = await state.get_data()
    if data.get("editing"):
        session = SessionLocal()
        user = ensure_user(session, query.from_user.id)
        goal = user.goal or Goal()
        user.goal = goal
        goal.body_fat = int(value) if value != "unknown" else None
        session.commit()
        session.close()
        await state.clear()
        await query.message.edit_text(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
    else:
        if query.message.photo:
            await _delete_message_safely(
                query.message.bot,
                query.message.chat.id,
                query.message.message_id,
            )
            sent = await query.message.answer(
                GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb()
            )
            await state.update_data(msg_id=sent.message_id)
        else:
            await query.message.edit_text(
                GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb()
            )
            await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.activity)
    await query.answer()


async def goal_set_activity(query: types.CallbackQuery, state: FSMContext):
    value = query.data.split(":")[1]
    await state.update_data(
        work_intensity=value,
        training_level=None,
        msg_id=query.message.message_id,
    )
    await query.message.edit_text(GOAL_CHOOSE_TRAINING, reply_markup=goal_training_kb())
    await state.set_state(GoalState.training)
    await query.answer()


async def goal_set_training(query: types.CallbackQuery, state: FSMContext):
    value = query.data.split(":")[1]
    data = await state.get_data()
    work = data.get("work_intensity") or "study"
    activity_value = f"{work}|{value}"
    await state.update_data(training_level=value, activity=activity_value)
    if data.get("editing"):
        session = SessionLocal()
        user = ensure_user(session, query.from_user.id)
        goal = user.goal or Goal()
        user.goal = goal
        goal.activity = activity_value
        calc = {
            "gender": goal.gender,
            "age": goal.age,
            "height": goal.height,
            "weight": goal.weight,
            "body_fat": goal.body_fat,
            "activity": activity_value,
            "work_intensity": work,
            "training_level": value,
            "target": goal.target,
            "plan": goal.plan,
        }
        cal, p, f, c = calculate_goal(calc)
        goal.calories, goal.protein, goal.fat, goal.carbs = cal, p, f, c
        session.commit()
        session.close()
        await state.clear()
        await query.message.edit_text(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
    else:
        await query.message.edit_text(GOAL_CHOOSE_TARGET, reply_markup=goal_target_kb())
        await state.set_state(GoalState.target)
    await query.answer()


async def goal_set_target(query: types.CallbackQuery, state: FSMContext):
    value = query.data.split(":")[1]
    await state.update_data(target=value)
    data = await state.get_data()
    if data.get("editing"):
        if value == "maintain":
            session = SessionLocal()
            user = ensure_user(session, query.from_user.id)
            goal = user.goal or Goal()
            user.goal = goal
            goal.target = value
            goal.plan = None
            work_level = training_level = None
            if isinstance(goal.activity, str) and "|" in goal.activity:
                work_level, training_level = goal.activity.split("|", 1)
            calc = {
                "gender": goal.gender,
                "age": goal.age,
                "height": goal.height,
                "weight": goal.weight,
                "body_fat": goal.body_fat,
                "activity": goal.activity,
                "work_intensity": work_level,
                "training_level": training_level,
                "target": goal.target,
                "plan": goal.plan,
            }
            cal, p, f, c = calculate_goal(calc)
            goal.calories, goal.protein, goal.fat, goal.carbs = cal, p, f, c
            session.commit()
            session.close()
            await state.clear()
            await query.message.edit_text(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
        else:
            await state.update_data(editing=True)
            if value == "loss":
                await query.message.edit_text(GOAL_CHOOSE_LOSS_PLAN, reply_markup=goal_plan_kb("loss"))
            else:
                await query.message.edit_text(GOAL_CHOOSE_GAIN_PLAN, reply_markup=goal_plan_kb("gain"))
            await state.set_state(GoalState.plan)
    else:
        if value == "maintain":
            cal, p, f, c = calculate_goal(data)
            await state.update_data(calories=cal, protein=p, fat=f, carbs=c)
            await query.message.edit_text(GOAL_CALC_PROGRESS)
            await query.message.edit_text(
                GOAL_RESULT.format(calories=cal, protein=p, fat=f, carbs=c),
                reply_markup=goal_confirm_kb(),
            )
        else:
            if value == "loss":
                await query.message.edit_text(GOAL_CHOOSE_LOSS_PLAN, reply_markup=goal_plan_kb("loss"))
            else:
                await query.message.edit_text(GOAL_CHOOSE_GAIN_PLAN, reply_markup=goal_plan_kb("gain"))
            await state.set_state(GoalState.plan)
    await query.answer()


async def goal_set_plan(query: types.CallbackQuery, state: FSMContext):
    value = query.data.split(":")[1]
    await state.update_data(plan=value)
    data = await state.get_data()
    if data.get("editing"):
        session = SessionLocal()
        user = ensure_user(session, query.from_user.id)
        goal = user.goal or Goal()
        user.goal = goal
        goal.plan = value
        work_level = training_level = None
        if isinstance(goal.activity, str) and "|" in goal.activity:
            work_level, training_level = goal.activity.split("|", 1)
        calc = {
            "gender": goal.gender,
            "age": goal.age,
            "height": goal.height,
            "weight": goal.weight,
            "body_fat": goal.body_fat,
            "activity": goal.activity,
            "work_intensity": work_level,
            "training_level": training_level,
            "target": goal.target,
            "plan": goal.plan,
        }
        cal, p, f, c = calculate_goal(calc)
        goal.calories, goal.protein, goal.fat, goal.carbs = cal, p, f, c
        session.commit()
        session.close()
        await state.clear()
        await query.message.edit_text(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
    else:
        cal, p, f, c = calculate_goal(data)
        await state.update_data(calories=cal, protein=p, fat=f, carbs=c)
        await query.message.edit_text(GOAL_CALC_PROGRESS)
        await query.message.edit_text(
            GOAL_RESULT.format(calories=cal, protein=p, fat=f, carbs=c),
            reply_markup=goal_confirm_kb(),
        )
    await query.answer()


async def goal_back(query: types.CallbackQuery, state: FSMContext):
    step = query.data.split(":")[1]
    if step == "gender":
        await goal_start(query, state)
    elif step == "age":
        await query.message.edit_text(GOAL_ENTER_AGE, reply_markup=goal_back_kb("gender"))
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.age)
    elif step == "height":
        await query.message.edit_text(GOAL_ENTER_HEIGHT, reply_markup=goal_back_kb("age"))
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.height)
    elif step == "weight":
        if query.message.photo:
            await _delete_message_safely(
                query.message.bot,
                query.message.chat.id,
                query.message.message_id,
            )
            sent = await query.message.answer(
                GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("height")
            )
            await state.update_data(msg_id=sent.message_id)
        else:
            await query.message.edit_text(
                GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("height")
            )
            await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.weight)
    elif step == "body_fat":
        await _show_goal_body_fat_prompt(
            query.message.bot,
            query.message.chat.id,
            state,
            query.message.message_id,
        )
        await state.set_state(GoalState.body_fat)
    elif step == "activity":
        await query.message.edit_text(GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb())
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.activity)
    elif step == "training":
        await query.message.edit_text(GOAL_CHOOSE_TRAINING, reply_markup=goal_training_kb())
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.training)
    elif step == "target":
        await query.message.edit_text(GOAL_CHOOSE_TARGET, reply_markup=goal_target_kb())
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.target)
    elif step == "edit":
        await state.clear()
        await query.message.edit_text(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
    await query.answer()


async def goal_confirm_save(query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cal, p, f, c = data["calories"], data["protein"], data["fat"], data["carbs"]
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    is_new = user.goal is None
    goal = user.goal or Goal()
    user.goal = goal
    goal.gender = data.get("gender")
    goal.age = data.get("age")
    goal.height = data.get("height")
    goal.weight = data.get("weight")
    goal.body_fat = data.get("body_fat")
    activity_value = data.get("activity")
    if not activity_value:
        work = data.get("work_intensity")
        training = data.get("training_level")
        if work or training:
            activity_value = f"{work or 'study'}|{training or 'none'}"
    goal.activity = activity_value
    goal.target = data.get("target")
    goal.plan = data.get("plan")
    goal.calories, goal.protein, goal.fat, goal.carbs = cal, p, f, c
    if is_new:
        goal.reminder_morning = True
        goal.reminder_evening = True
    session.commit()
    session.refresh(goal)
    summary = goal_summary_text(goal, session)
    session.close()
    await state.clear()
    await query.message.edit_text(summary, reply_markup=goals_main_kb())
    await query.answer()


async def goal_restart(query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(GOAL_CHOOSE_GENDER, reply_markup=goal_gender_kb())
    await state.set_state(GoalState.gender)
    await query.answer()


async def goal_edit_param(query: types.CallbackQuery, state: FSMContext):
    param = query.data.split(":")[1]
    await state.update_data(editing=True, msg_id=query.message.message_id)
    if param == "weight":
        await query.message.edit_text(GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("edit"))
        await state.set_state(GoalState.weight)
    elif param == "height":
        await query.message.edit_text(GOAL_ENTER_HEIGHT, reply_markup=goal_back_kb("edit"))
        await state.set_state(GoalState.height)
    elif param == "age":
        await query.message.edit_text(GOAL_ENTER_AGE, reply_markup=goal_back_kb("edit"))
        await state.set_state(GoalState.age)
    elif param == "activity":
        await state.update_data(work_intensity=None, training_level=None)
        await query.message.edit_text(GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb())
        await state.set_state(GoalState.activity)
    elif param == "target":
        await query.message.edit_text(GOAL_CHOOSE_TARGET, reply_markup=goal_target_kb())
        await state.set_state(GoalState.target)
    await query.answer()


async def goal_recalc(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal
    if goal:
        data = {
            "gender": goal.gender,
            "age": goal.age,
            "height": goal.height,
            "weight": goal.weight,
            "body_fat": goal.body_fat,
            "activity": goal.activity,
            "target": goal.target,
            "plan": goal.plan,
        }
        cal, p, f, c = calculate_goal(data)
        goal.calories, goal.protein, goal.fat, goal.carbs = cal, p, f, c
        session.commit()
        await query.message.edit_text(
            goal_summary_text(goal, session), reply_markup=goals_main_kb()
        )
    else:
        await query.message.edit_text(GOAL_INTRO_TEXT, reply_markup=goal_start_kb())
    session.close()
    await query.answer()


async def goal_trends(query: types.CallbackQuery):
    days = int(query.data.split(":")[1])
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    text = goal_trends_report(user, days, session)
    await query.message.edit_text(text, reply_markup=goal_trends_kb(days))
    session.close()
    await query.answer()


async def goal_reminders(query: types.CallbackQuery, state: FSMContext):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal or Goal()
    user.goal = goal

    if user.timezone is None:
        utc = datetime.utcnow().strftime("%H:%M")
        await query.message.edit_text(
            TZ_PROMPT.format(utc_time=utc),
            reply_markup=back_to_goal_reminders_kb(),
        )
        await state.update_data(
            prompt_id=query.message.message_id, return_to="main"
        )
        await state.set_state(GoalReminderState.waiting_timezone)
        session.commit()
        session.close()
        await query.answer()
        return

    now = datetime.utcnow() + timedelta(minutes=user.timezone or 0)
    text = GOAL_REMINDERS_TEXT.format(time=now.strftime("%H:%M"))
    await query.message.edit_text(text, reply_markup=goal_reminders_kb(goal))
    session.commit()
    session.close()
    await query.answer()


async def goal_toggle(query: types.CallbackQuery):
    field = query.data.split(":")[1]
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal or Goal()
    user.goal = goal
    if field == "morning":
        goal.reminder_morning = not goal.reminder_morning
    else:
        goal.reminder_evening = not goal.reminder_evening
    session.commit()
    text = GOAL_REMINDERS_TEXT.format(
        time=(datetime.utcnow() + timedelta(minutes=user.timezone or 0)).strftime("%H:%M")
    )
    await query.message.edit_text(text, reply_markup=goal_reminders_kb(goal))
    session.close()
    await query.answer()


async def goal_time(query: types.CallbackQuery, state: FSMContext):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    utc = datetime.utcnow().strftime("%H:%M")
    await query.message.edit_text(
        TZ_PROMPT.format(utc_time=utc),
        reply_markup=back_to_goal_reminders_settings_kb(),
    )
    await state.update_data(
        prompt_id=query.message.message_id, return_to="settings"
    )
    await state.set_state(GoalReminderState.waiting_timezone)
    await query.answer()
    session.close()


async def goal_timezone(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
    except Exception:
        await message.answer(INVALID_TIME)
        return
    user_time = hours * 60 + minutes
    utc_now = datetime.utcnow()
    server_minutes = utc_now.hour * 60 + utc_now.minute
    diff = user_time - server_minutes
    if diff <= -720:
        diff += 1440
    if diff >= 720:
        diff -= 1440
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    goal = user.goal or Goal()
    user.goal = goal
    user.timezone = diff
    session.commit()
    data = await state.get_data()
    prompt_id = data.get("prompt_id")
    return_to = data.get("return_to", "settings")
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    local_dt = datetime.utcnow() + timedelta(minutes=user.timezone or 0)
    local = local_dt.strftime("%H:%M")
    if return_to == "main":
        text = GOAL_REMINDERS_TEXT.format(time=local)
        markup = goal_reminders_kb(goal)
    else:
        text = TIME_CURRENT.format(local_time=local)
        markup = goal_reminders_settings_kb(user)
    if prompt_id:
        await message.bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=prompt_id,
            reply_markup=markup,
        )
    else:
        await message.answer(text, reply_markup=markup)
    session.close()


async def goal_reminder_settings(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    local = (datetime.utcnow() + timedelta(minutes=user.timezone or 0)).strftime("%H:%M")
    await query.message.edit_text(
        TIME_CURRENT.format(local_time=local),
        reply_markup=goal_reminders_settings_kb(user),
    )
    session.close()
    await query.answer()


async def goal_set_time_prompt(
    query: types.CallbackQuery, state: FSMContext, field: str, name: str
):
    await query.message.edit_text(SET_TIME_PROMPT.format(name=name))
    await query.message.edit_reply_markup(
        reply_markup=back_to_goal_reminders_settings_kb()
    )
    await state.update_data(prompt_id=query.message.message_id)
    await state.set_state(getattr(GoalReminderState, field))
    await query.answer()


async def goal_set_morning_prompt(query: types.CallbackQuery, state: FSMContext):
    await goal_set_time_prompt(query, state, "set_morning", BTN_MORNING)


async def goal_set_evening_prompt(query: types.CallbackQuery, state: FSMContext):
    await goal_set_time_prompt(query, state, "set_evening", BTN_EVENING)


async def goal_process_time(
    message: types.Message, state: FSMContext, attr: str
):
    try:
        parts = message.text.strip().split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
    except Exception:
        await message.answer(INVALID_TIME)
        return
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    setattr(user, attr, f"{hours:02d}:{minutes:02d}")
    session.commit()
    data = await state.get_data()
    prompt_id = data.get("prompt_id")
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    local = (
        datetime.utcnow() + timedelta(minutes=user.timezone or 0)
    ).strftime("%H:%M")
    text = TIME_CURRENT.format(local_time=local)
    if prompt_id:
        await message.bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=prompt_id,
            reply_markup=goal_reminders_settings_kb(user),
        )
    else:
        await message.answer(text, reply_markup=goal_reminders_settings_kb(user))
    session.close()


async def goal_process_morning_time(message: types.Message, state: FSMContext):
    await goal_process_time(message, state, "morning_time")


async def goal_process_evening_time(message: types.Message, state: FSMContext):
    await goal_process_time(message, state, "evening_time")


async def goal_stop(query: types.CallbackQuery):
    await query.message.edit_text(GOAL_STOP_PROMPT, reply_markup=goal_stop_confirm_kb())
    await query.answer()


async def goal_stop_confirm(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    if user.goal:
        session.delete(user.goal)
        session.commit()
    session.close()
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.answer(GOAL_STOP_DONE, reply_markup=main_menu_kb())
    await query.answer()


async def goals_main(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal
    if goal:
        await query.message.edit_text(
            goal_summary_text(goal, session), reply_markup=goals_main_kb()
        )
    else:
        await query.message.edit_text(GOAL_INTRO_TEXT, reply_markup=goal_start_kb())
    session.close()
    await query.answer()


def register(dp: Dispatcher):
    dp.callback_query.register(open_goals, F.data.in_(["goals", "goals_main"]))
    dp.callback_query.register(goal_start, F.data == "goal_start")
    dp.callback_query.register(goal_cancel, F.data == "goal_cancel")
    dp.callback_query.register(goal_set_gender, F.data.startswith("goal_gender:"))
    dp.message.register(process_age, StateFilter(GoalState.age))
    dp.message.register(process_height, StateFilter(GoalState.height))
    dp.message.register(process_weight, StateFilter(GoalState.weight))
    dp.callback_query.register(goal_set_body_fat, F.data.startswith("goal_bodyfat:"))
    dp.callback_query.register(goal_set_activity, F.data.startswith("goal_activity:"))
    dp.callback_query.register(goal_set_training, F.data.startswith("goal_training:"))
    dp.callback_query.register(goal_set_target, F.data.startswith("goal_target:"))
    dp.callback_query.register(goal_set_plan, F.data.startswith("goal_plan:"))
    dp.callback_query.register(goal_back, F.data.startswith("goal_back:"))
    dp.callback_query.register(goal_confirm_save, F.data == "goal_save")
    dp.callback_query.register(goal_restart, F.data == "goal_restart")
    dp.callback_query.register(goal_edit_param, F.data.startswith("goal_edit:"))
    dp.callback_query.register(goal_recalc, F.data == "goal_recalc")
    dp.callback_query.register(goal_trends, F.data.startswith("goal_trends:"))
    dp.callback_query.register(
        goal_reminders, F.data.in_(["goal_reminders", "goal_reminders_back"])
    )
    dp.callback_query.register(goal_reminder_settings, F.data == "goal_reminder_settings")
    dp.callback_query.register(goal_toggle, F.data.startswith("goal_toggle:"))
    dp.callback_query.register(goal_set_morning_prompt, F.data == "goal_set_morning")
    dp.callback_query.register(goal_set_evening_prompt, F.data == "goal_set_evening")
    dp.callback_query.register(goal_time, F.data == "goal_time")
    dp.callback_query.register(goal_stop, F.data == "goal_stop")
    dp.callback_query.register(goal_stop_confirm, F.data == "goal_stop_confirm")
    dp.callback_query.register(goals_main, F.data == "goals_main")

    dp.message.register(goal_timezone, StateFilter(GoalReminderState.waiting_timezone))
    dp.message.register(
        goal_process_morning_time, StateFilter(GoalReminderState.set_morning)
    )
    dp.message.register(
        goal_process_evening_time, StateFilter(GoalReminderState.set_evening)
    )

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest

from ..database import SessionLocal, Goal, get_option_bool
from ..subscriptions import ensure_user
from ..keyboards import (
    goal_start_kb,
    goal_gender_kb,
    goal_back_kb,
    goal_body_fat_kb,
    goal_activity_kb,
    goal_target_kb,
    goal_plan_kb,
    goal_confirm_kb,
    goals_main_kb,
    goal_edit_kb,
    goal_trends_kb,
    goal_reminders_kb,
    goal_stop_confirm_kb,
    main_menu_kb,
)
from ..states import GoalState
from ..texts import (
    GOAL_INTRO_TEXT,
    GOAL_CHOOSE_GENDER,
    GOAL_ENTER_AGE,
    GOAL_ENTER_HEIGHT,
    GOAL_ENTER_WEIGHT,
    GOAL_CHOOSE_BODY_FAT,
    GOAL_CHOOSE_ACTIVITY,
    GOAL_CHOOSE_TARGET,
    GOAL_CHOOSE_LOSS_PLAN,
    GOAL_CHOOSE_GAIN_PLAN,
    GOAL_CALC_PROGRESS,
    GOAL_RESULT,
    GOAL_CURRENT,
    GOAL_EDIT_PROMPT,
    GOAL_TRENDS,
    GOAL_REMINDERS_TEXT,
    GOAL_STOP_PROMPT,
    GOAL_STOP_DONE,
    INPUT_NUMBER_PROMPT,
    INPUT_RANGE_ERROR,
    FEATURE_DISABLED,
)
from datetime import datetime, timedelta


def calculate_goal(data: dict) -> tuple[int, int, int, int]:
    gender = data.get("gender", "male")
    age = int(data.get("age", 0))
    height = int(data.get("height", 0))
    weight = float(data.get("weight", 0))
    body_fat = data.get("body_fat")
    activity = data.get("activity", "sedentary")
    target = data.get("target", "maintain")
    plan = data.get("plan")

    if body_fat is not None:
        lbm = weight * (1 - float(body_fat) / 100)
        bmr = 370 + 21.6 * lbm
    else:
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
    factors = {
        "sedentary": 1.2,
        "low": 1.375,
        "med": 1.55,
        "high": 1.725,
        "very_high": 1.9,
    }
    maintenance = bmr * factors.get(activity, 1.2)
    calories = maintenance
    ratios = (0.3, 0.3, 0.4)
    if target == "loss":
        if plan == "fast":
            calories = maintenance * 0.8
        elif plan == "protein":
            calories = maintenance * 0.85
            ratios = (0.4, 0.3, 0.3)
        else:
            calories = maintenance * 0.85
    elif target == "gain":
        if plan == "fast":
            calories = maintenance * 1.2
        elif plan == "protein_carb":
            calories = maintenance * 1.15
            ratios = (0.3, 0.2, 0.5)
        else:
            calories = maintenance * 1.15
    calories = int(calories)
    protein = int(calories * ratios[0] / 4)
    fat = int(calories * ratios[1] / 9)
    carbs = int(calories * ratios[2] / 4)
    return calories, protein, fat, carbs


def goal_summary_text(goal: Goal) -> str:
    eaten = p_eaten = f_eaten = c_eaten = 0
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


async def open_goals(query: types.CallbackQuery, state: FSMContext):
    if not get_option_bool("feat_goals"):
        await query.answer(FEATURE_DISABLED, show_alert=True)
        return
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal
    if not goal or not goal.calories:
        await query.message.edit_text(GOAL_INTRO_TEXT, reply_markup=goal_start_kb())
    else:
        await query.message.edit_text(goal_summary_text(goal), reply_markup=goals_main_kb())
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
        await message.answer(GOAL_ENTER_HEIGHT, reply_markup=goal_back_kb("age"))
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
        await message.answer(GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("height"))
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
        if msg_id:
            await message.bot.edit_message_text(
                GOAL_CHOOSE_BODY_FAT,
                chat_id=message.chat.id,
                message_id=msg_id,
                reply_markup=goal_body_fat_kb(),
            )
        else:
            await message.answer(GOAL_CHOOSE_BODY_FAT, reply_markup=goal_body_fat_kb())
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
        await query.message.edit_text(GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb())
        await state.set_state(GoalState.activity)
    await query.answer()


async def goal_set_activity(query: types.CallbackQuery, state: FSMContext):
    value = query.data.split(":")[1]
    await state.update_data(activity=value)
    data = await state.get_data()
    if data.get("editing"):
        session = SessionLocal()
        user = ensure_user(session, query.from_user.id)
        if not user.goal:
            user.goal = Goal()
        user.goal.activity = value
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
            calc = {
                "gender": goal.gender,
                "age": goal.age,
                "height": goal.height,
                "weight": goal.weight,
                "body_fat": goal.body_fat,
                "activity": goal.activity,
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
        calc = {
            "gender": goal.gender,
            "age": goal.age,
            "height": goal.height,
            "weight": goal.weight,
            "body_fat": goal.body_fat,
            "activity": goal.activity,
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
        await query.message.edit_text(GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("height"))
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.weight)
    elif step == "body_fat":
        await query.message.edit_text(GOAL_CHOOSE_BODY_FAT, reply_markup=goal_body_fat_kb())
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.body_fat)
    elif step == "activity":
        await query.message.edit_text(GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb())
        await state.update_data(msg_id=query.message.message_id)
        await state.set_state(GoalState.activity)
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
    goal.activity = data.get("activity")
    goal.target = data.get("target")
    goal.plan = data.get("plan")
    goal.calories, goal.protein, goal.fat, goal.carbs = cal, p, f, c
    if is_new:
        goal.reminder_morning = True
        goal.reminder_evening = True
    session.commit()
    session.refresh(goal)
    summary = goal_summary_text(goal)
    session.close()
    await state.clear()
    await query.message.edit_text(summary, reply_markup=goals_main_kb())
    await query.answer()


async def goal_restart(query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(GOAL_CHOOSE_GENDER, reply_markup=goal_gender_kb())
    await state.set_state(GoalState.gender)
    await query.answer()


async def goal_edit_menu(query: types.CallbackQuery):
    await query.message.edit_text(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
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
        await query.message.edit_text(goal_summary_text(goal), reply_markup=goals_main_kb())
    else:
        await query.message.edit_text(GOAL_INTRO_TEXT, reply_markup=goal_start_kb())
    session.close()
    await query.answer()


async def goal_trends(query: types.CallbackQuery):
    days = int(query.data.split(":")[1])
    text = GOAL_TRENDS.format(days=days, balance=0, p=0, p_goal=0, f=0, f_goal=0, c=0, c_goal=0)
    await query.message.edit_text(text, reply_markup=goal_trends_kb(days))
    await query.answer()


async def goal_reminders(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal or Goal()
    user.goal = goal
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


async def goal_time(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal or Goal()
    now = datetime.utcnow() + timedelta(minutes=user.timezone or 0)
    text = GOAL_REMINDERS_TEXT.format(time=now.strftime("%H:%M"))
    try:
        await query.message.edit_text(text, reply_markup=goal_reminders_kb(goal))
    except TelegramBadRequest:
        await query.answer("Время обновлено")
    else:
        await query.answer()
    session.close()


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
        await query.message.edit_text(goal_summary_text(goal), reply_markup=goals_main_kb())
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
    dp.callback_query.register(goal_set_target, F.data.startswith("goal_target:"))
    dp.callback_query.register(goal_set_plan, F.data.startswith("goal_plan:"))
    dp.callback_query.register(goal_back, F.data.startswith("goal_back:"))
    dp.callback_query.register(goal_confirm_save, F.data == "goal_save")
    dp.callback_query.register(goal_restart, F.data == "goal_restart")
    dp.callback_query.register(goal_edit_menu, F.data == "goal_edit_menu")
    dp.callback_query.register(goal_edit_param, F.data.startswith("goal_edit:"))
    dp.callback_query.register(goal_recalc, F.data == "goal_recalc")
    dp.callback_query.register(goal_trends, F.data.startswith("goal_trends:"))
    dp.callback_query.register(goal_reminders, F.data == "goal_reminders")
    dp.callback_query.register(goal_toggle, F.data.startswith("goal_toggle:"))
    dp.callback_query.register(goal_time, F.data == "goal_time")
    dp.callback_query.register(goal_stop, F.data == "goal_stop")
    dp.callback_query.register(goal_stop_confirm, F.data == "goal_stop_confirm")
    dp.callback_query.register(goals_main, F.data == "goals_main")

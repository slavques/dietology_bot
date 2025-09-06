from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from ..database import SessionLocal, Goal, get_option_bool
from ..subscriptions import ensure_user
from ..keyboards import (
    goal_start_kb,
    goal_gender_kb,
    goal_back_kb,
    goal_activity_kb,
    goal_target_kb,
    goal_confirm_kb,
    goals_main_kb,
    goal_edit_kb,
    goal_trends_kb,
    goal_reminders_kb,
)
from ..states import GoalState
from ..texts import (
    GOAL_INTRO_TEXT,
    GOAL_CHOOSE_GENDER,
    GOAL_ENTER_AGE,
    GOAL_ENTER_HEIGHT,
    GOAL_ENTER_WEIGHT,
    GOAL_CHOOSE_ACTIVITY,
    GOAL_CHOOSE_TARGET,
    GOAL_CALC_PROGRESS,
    GOAL_RESULT,
    GOAL_CURRENT,
    GOAL_EDIT_PROMPT,
    GOAL_TRENDS,
    GOAL_REMINDERS_TEXT,
    FEATURE_DISABLED,
)
from datetime import datetime, timedelta


def calculate_goal(data: dict) -> tuple[int, int, int, int]:
    gender = data.get("gender", "male")
    age = int(data.get("age", 0))
    height = int(data.get("height", 0))
    weight = float(data.get("weight", 0))
    activity = data.get("activity", "low")
    target = data.get("target", "maintain")

    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    factors = {"low": 1.2, "med": 1.55, "high": 1.725}
    calories = bmr * factors.get(activity, 1.2)
    if target == "loss":
        calories -= 500
    elif target == "gain":
        calories += 500
    calories = int(calories)
    protein = int(calories * 0.3 / 4)
    fat = int(calories * 0.3 / 9)
    carbs = int(calories * 0.4 / 4)
    return calories, protein, fat, carbs


def goal_summary_text(goal: Goal) -> str:
    eaten = 0
    remain = (goal.calories or 0) - eaten
    return GOAL_CURRENT.format(
        cal=goal.calories or 0,
        p=goal.protein or 0,
        f=goal.fat or 0,
        c=goal.carbs or 0,
        eaten=eaten,
        remain=remain,
    )


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
    await state.update_data(gender=value)
    await query.message.edit_text(GOAL_ENTER_AGE, reply_markup=goal_back_kb("gender"))
    await state.set_state(GoalState.age)
    await query.answer()


async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
    except ValueError:
        await message.answer("Введите число")
        return
    await state.update_data(age=age)
    await message.answer(GOAL_ENTER_HEIGHT, reply_markup=goal_back_kb("age"))
    await state.set_state(GoalState.height)


async def process_height(message: types.Message, state: FSMContext):
    try:
        height = int(message.text)
    except ValueError:
        await message.answer("Введите число")
        return
    await state.update_data(height=height)
    await message.answer(GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("height"))
    await state.set_state(GoalState.weight)


async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите число")
        return
    await state.update_data(weight=weight)
    data = await state.get_data()
    if data.get("editing"):
        session = SessionLocal()
        user = ensure_user(session, message.from_user.id)
        if not user.goal:
            user.goal = Goal()
        user.goal.weight = weight
        session.commit()
        session.close()
        await state.clear()
        await message.answer(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
    else:
        await message.answer(GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb())
        await state.set_state(GoalState.activity)


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
        session = SessionLocal()
        user = ensure_user(session, query.from_user.id)
        goal = user.goal or Goal()
        user.goal = goal
        goal.target = value
        calc = {
            "gender": goal.gender,
            "age": goal.age,
            "height": goal.height,
            "weight": goal.weight,
            "activity": goal.activity,
            "target": goal.target,
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
        await state.set_state(GoalState.age)
    elif step == "height":
        await query.message.edit_text(GOAL_ENTER_HEIGHT, reply_markup=goal_back_kb("age"))
        await state.set_state(GoalState.height)
    elif step == "weight":
        await query.message.edit_text(GOAL_ENTER_WEIGHT, reply_markup=goal_back_kb("height"))
        await state.set_state(GoalState.weight)
    elif step == "activity":
        await query.message.edit_text(GOAL_CHOOSE_ACTIVITY, reply_markup=goal_activity_kb())
        await state.set_state(GoalState.activity)
    elif step == "edit":
        await state.clear()
        await query.message.edit_text(GOAL_EDIT_PROMPT, reply_markup=goal_edit_kb())
    await query.answer()


async def goal_confirm_save(query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cal, p, f, c = data["calories"], data["protein"], data["fat"], data["carbs"]
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal or Goal()
    user.goal = goal
    goal.gender = data.get("gender")
    goal.age = data.get("age")
    goal.height = data.get("height")
    goal.weight = data.get("weight")
    goal.activity = data.get("activity")
    goal.target = data.get("target")
    goal.calories, goal.protein, goal.fat, goal.carbs = cal, p, f, c
    session.commit()
    session.close()
    await state.clear()
    await query.message.edit_text(goal_summary_text(goal), reply_markup=goals_main_kb())
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
    await state.update_data(editing=True)
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
            "activity": goal.activity,
            "target": goal.target,
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
    now = datetime.utcnow() + timedelta(hours=3)
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
        time=(datetime.utcnow() + timedelta(hours=3)).strftime("%H:%M")
    )
    await query.message.edit_text(text, reply_markup=goal_reminders_kb(goal))
    session.close()
    await query.answer()


async def goal_time(query: types.CallbackQuery):
    session = SessionLocal()
    user = ensure_user(session, query.from_user.id)
    goal = user.goal or Goal()
    now = datetime.utcnow() + timedelta(hours=3)
    text = GOAL_REMINDERS_TEXT.format(time=now.strftime("%H:%M"))
    await query.message.edit_text(text, reply_markup=goal_reminders_kb(goal))
    session.close()
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
    dp.callback_query.register(goal_set_activity, F.data.startswith("goal_activity:"))
    dp.callback_query.register(goal_set_target, F.data.startswith("goal_target:"))
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
    dp.callback_query.register(goals_main, F.data == "goals_main")

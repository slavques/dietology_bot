from aiogram.fsm.state import StatesGroup, State

class EditMeal(StatesGroup):
    waiting_input = State()


class ManualMeal(StatesGroup):
    waiting_text = State()


class LookupMeal(StatesGroup):
    """Flow when choosing product and entering weight from FatSecret."""

    choosing = State()
    entering_weight = State()
    entering_query = State()


class AdminState(StatesGroup):
    waiting_broadcast = State()
    waiting_broadcast_support = State()
    waiting_user_id = State()
    waiting_days = State()
    waiting_days_all = State()
    waiting_block_id = State()
    waiting_trial_days = State()
    waiting_trial_user_id = State()
    waiting_trial_start_days = State()
    waiting_grade_days = State()
    waiting_grade_user_id = State()
    waiting_view_id = State()
    waiting_comment_text = State()
    waiting_discount_id = State()
    waiting_discount_confirm = State()


class ReminderState(StatesGroup):
    waiting_timezone = State()
    set_morning = State()
    set_day = State()
    set_evening = State()


class GoalState(StatesGroup):
    """States for nutrition goal setup and editing."""

    gender = State()
    age = State()
    height = State()
    weight = State()
    body_fat = State()
    activity = State()
    target = State()
    plan = State()



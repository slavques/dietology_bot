from aiogram.fsm.state import StatesGroup, State

class EditMeal(StatesGroup):
    waiting_input = State()


class ManualMeal(StatesGroup):
    waiting_text = State()


class AdminState(StatesGroup):
    waiting_broadcast = State()
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


class ReminderState(StatesGroup):
    waiting_timezone = State()
    set_morning = State()
    set_day = State()
    set_evening = State()



from aiogram.fsm.state import StatesGroup, State

class EditMeal(StatesGroup):
    waiting_input = State()


class AdminState(StatesGroup):
    waiting_broadcast = State()

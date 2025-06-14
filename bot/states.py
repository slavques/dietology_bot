from aiogram.fsm.state import StatesGroup, State

class EditMeal(StatesGroup):
    waiting_input = State()

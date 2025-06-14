from aiogram.dispatcher.filters.state import StatesGroup, State

class EditMeal(StatesGroup):
    waiting_input = State()

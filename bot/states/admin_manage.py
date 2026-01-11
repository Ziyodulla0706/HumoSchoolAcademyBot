from aiogram.fsm.state import State, StatesGroup

class AdminManageParentState(StatesGroup):
    waiting_query = State()  # телефон или telegram id

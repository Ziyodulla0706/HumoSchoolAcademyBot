from aiogram.fsm.state import StatesGroup, State

class TeacherMessageState(StatesGroup):
    choosing_class = State()
    choosing_type = State()
    entering_text = State()

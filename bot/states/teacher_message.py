from aiogram.fsm.state import State, StatesGroup

class TeacherMessageState(StatesGroup):
    choosing_class = State()
    choosing_type = State()
    entering_text = State()
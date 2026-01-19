from aiogram.fsm.state import StatesGroup, State


class CommentState(StatesGroup):
    choosing_class = State()
    choosing_student = State()
    choosing_type = State()
    entering_text = State()

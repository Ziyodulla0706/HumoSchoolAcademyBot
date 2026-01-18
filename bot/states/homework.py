from aiogram.fsm.state import StatesGroup, State


class HomeworkState(StatesGroup):
    choosing_class = State()
    choosing_subject = State()
    entering_text = State()
    entering_due_date = State()

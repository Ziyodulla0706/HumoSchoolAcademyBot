from aiogram.fsm.state import StatesGroup, State


class GradeState(StatesGroup):
    choosing_class = State()
    choosing_student = State()
    choosing_subject = State()
    entering_grade = State()

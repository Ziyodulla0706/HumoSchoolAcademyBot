from aiogram.fsm.state import StatesGroup, State


class AttendanceState(StatesGroup):
    choosing_class = State()
    choosing_date = State()
    marking_attendance = State()

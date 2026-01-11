from aiogram.fsm.state import StatesGroup, State

class TeacherRegistrationState(StatesGroup):
    waiting_full_name = State()
    waiting_classes = State()

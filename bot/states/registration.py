from aiogram.fsm.state import State, StatesGroup

class RegistrationState(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    
class AddChildState(StatesGroup):
    waiting_child_name = State()
    waiting_class_name = State()
    
class PickupState(StatesGroup):
    choosing_child = State()
    choosing_time = State()
    
class UpdatePhoneState(StatesGroup):
    waiting_phone = State()

class UpdateFullNameState(StatesGroup):
    waiting_full_name = State()

class UpdateChildNameState(StatesGroup):
    choosing_child = State()
    waiting_new_name = State()
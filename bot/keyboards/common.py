from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def role_selection_keyboard(is_admin: bool = False):
    """Клавиатура выбора роли при старте"""
    keyboard = [
        [KeyboardButton(text="👨‍👩‍👧 Я родитель")],
        [KeyboardButton(text="👨‍🏫 Я учитель")],
    ]
    
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Я администратор")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

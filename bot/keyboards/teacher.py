from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

def teacher_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отметить посещаемость")],
            [KeyboardButton(text="📝 Поставить оценку")],
            [KeyboardButton(text="💬 Добавить комментарий ученику")],
            [KeyboardButton(text="📚 Домашнее задание")],
            [KeyboardButton(text="✉️ Сообщение родителям")],
            [KeyboardButton(text="📚 Мои классы")],
            [KeyboardButton(text="🚪 Выйти из режима учителя")],
        ],
        resize_keyboard=True
    )

def teacher_classes_keyboard(classes: list[str]):
    rows = []
    for cls in classes:
        rows.append([InlineKeyboardButton(text=cls, callback_data=f"tmsg_class:{cls}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def teacher_message_type_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📌 Поведение", callback_data="tmsg_type:behavior")],
            [InlineKeyboardButton(text="🕒 Посещаемость", callback_data="tmsg_type:attendance")],
            [InlineKeyboardButton(text="📊 Успеваемость", callback_data="tmsg_type:performance")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="tmsg_cancel")]
        ]
    )


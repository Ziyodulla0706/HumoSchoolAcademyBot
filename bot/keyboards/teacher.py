from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def teacher_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Мои классы")],
            [KeyboardButton(text="✉️ Сообщение родителям")]
        ],
        resize_keyboard=True
    )

def teacher_classes_keyboard(classes: list[str]):
    # inline-кнопки с выбором класса
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
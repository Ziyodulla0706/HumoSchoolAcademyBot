from aiogram.types import ReplyKeyboardMarkup, KeyboardButton,InlineKeyboardMarkup,InlineKeyboardButton


def parent_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Я еду за ребёнком")],
            [KeyboardButton(text="Мои дети")],
            [KeyboardButton(text="Добавить ребёнка")],
            [KeyboardButton(text="Я учитель")],
            [KeyboardButton(text="Изменить номер телефона")],
        ],
        resize_keyboard=True
    )

def children_inline_keyboard(children):
    keyboard = []
    for c in children:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{c.full_name} ({c.class_name})",
                callback_data=f"pickup_child:{c.id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def time_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="5 минут", callback_data="pickup_time:5")],
            [InlineKeyboardButton(text="10 минут", callback_data="pickup_time:10")],
            [InlineKeyboardButton(text="15 минут", callback_data="pickup_time:15")]
        ]
    )    
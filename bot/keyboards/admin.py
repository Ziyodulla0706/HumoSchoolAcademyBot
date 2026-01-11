from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def approve_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=f"approve_user:{user_id}"
                )
            ]
        ]
    )


def guard_actions_keyboard(pickup_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Передан",
                    callback_data=f"pickup_done:{pickup_id}"
                )
            ]
        ]
    )


def teacher_verify_keyboard(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"teacher_verify:{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"teacher_reject:{user_id}")
            ]
        ]
    )
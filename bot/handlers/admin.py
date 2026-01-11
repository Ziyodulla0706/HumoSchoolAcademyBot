from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.config import ADMIN_IDS
from bot.db.database import SessionLocal
from bot.db.models import User, PickupRequest
from aiogram.types import CallbackQuery
from aiogram.filters import Command
from bot.keyboards.admin import approve_user_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("approve"))
async def approve_list(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        return

    session = SessionLocal()

    users = session.query(User).filter(
        User.is_verified == False
    ).all()

    if not users:
        await message.answer("Нет пользователей, ожидающих подтверждения.")
        session.close()
        return

    for user in users:
        await message.answer(
            f"ФИО: {user.full_name}\n"
            f"Телефон: {user.phone}",
            reply_markup=approve_user_keyboard(user.id)
        )

    session.close()

@router.callback_query(lambda c: c.data.startswith("approve_user:"))
async def approve_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    user = session.query(User).filter(User.id == user_id).first()

    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        session.close()
        return

    user.is_verified = True
    session.commit()

    await callback.message.edit_text(
        f"Пользователь {user.full_name} подтверждён."
    )

    # уведомляем родителя
    try:
        await callback.bot.send_message(
            user.telegram_id,
            "Ваша регистрация подтверждена. Теперь вы можете пользоваться ботом."
        )
    except:
        pass

    session.close()
    await callback.answer("Готово")

from aiogram.types import CallbackQuery
from datetime import datetime

@router.callback_query(lambda c: c.data.startswith("pickup_done:"))
async def pickup_done(callback: CallbackQuery):
    pickup_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    try:
        pickup = session.query(PickupRequest).filter(PickupRequest.id == pickup_id).first()
        if not pickup:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        pickup.status = "DONE"
        pickup.updated_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()

    await callback.message.edit_text("✅ Отмечено: ребёнок передан родителю.")
    await callback.answer("Готово.")



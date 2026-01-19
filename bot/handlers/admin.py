from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from bot.config import ADMIN_IDS
from bot.db.database import SessionLocal
from bot.db.models import User, PickupRequest, Child
from bot.keyboards.admin import approve_user_keyboard
from datetime import datetime

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("approve"))
async def approve_list(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        return

    session = SessionLocal()
    try:
        users = session.query(User).filter(
            User.is_verified == False
        ).all()

        if not users:
            await message.answer("Нет заявок на подтверждение.")
            return

        for user in users:
            await message.answer(
                f"ФИО: {user.full_name}\n"
                f"Телефон: {user.phone}",
                reply_markup=approve_user_keyboard(user.id)
            )
    finally:
        session.close()

@router.callback_query(lambda c: c.data.startswith("approve_user:"))
async def approve_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
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

        await callback.answer("Готово")
    finally:
        session.close()


@router.callback_query(lambda c: c.data.startswith("pickup_done:"))
async def pickup_done(callback: CallbackQuery):
    pickup_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    try:
        pickup = session.query(PickupRequest).filter(PickupRequest.id == pickup_id).first()
        if not pickup:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        # Получаем данные о родителе и ребёнке
        parent = session.query(User).filter(User.id == pickup.parent_id).first()
        child = session.query(Child).filter(Child.id == pickup.child_id).first()

        if not parent or not child:
            await callback.answer("Ошибка: данные не найдены.", show_alert=True)
            return

        pickup.status = "DONE"
        pickup.updated_at = datetime.utcnow()
        session.commit()

        # Формируем обновлённое сообщение с сохранением всей информации
        # Пересобираем сообщение из данных БД, чтобы сохранить всю информацию
        new_text = (
            f"📌 Выдача ученика\n"
            f"Родитель: {parent.full_name}\n"
            f"Ученик: {child.full_name} ({child.class_name})\n"
            f"Ожидается через: {pickup.arrival_minutes} мин.\n"
            f"✅ Статус: Передан родителю"
        )

        # Обновляем сообщение, убирая клавиатуру
        await callback.message.edit_text(new_text, reply_markup=None)
    finally:
        session.close()

    await callback.answer("Готово.")



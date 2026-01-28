from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from bot.config import ADMIN_IDS
from bot.db.database import SessionLocal
from bot.db.models import User, PickupRequest, Child
from bot.keyboards.admin import approve_user_keyboard
from datetime import datetime, date

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
    # Доступ только для администраторов/ответственных сотрудников
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    pickup_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    try:
        pickup = session.query(PickupRequest).filter(PickupRequest.id == pickup_id).first()
        if not pickup:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        # Если уже отмечено как переданный — ничего не делаем
        if pickup.status == "HANDED_OVER":
            await callback.answer("Ученик уже отмечен как переданный.")
            return

        # Получаем данные о родителе и ребёнке
        parent = session.query(User).filter(User.id == pickup.parent_id).first()
        child = session.query(Child).filter(Child.id == pickup.child_id).first()

        if not parent or not child:
            await callback.answer("Ошибка: данные не найдены.", show_alert=True)
            return

        now = datetime.utcnow()
        pickup.status = "HANDED_OVER"
        pickup.updated_at = now
        pickup.handed_over_at = now
        pickup.handed_over_by = callback.from_user.id
        session.commit()

        # Формируем обновлённое сообщение с сохранением всей информации
        new_text = (
            "📌 Выдача ученика\n"
            "🟢 РЕБЕНОК ПЕРЕДАН\n"
            f"Родитель: {parent.full_name}\n"
            f"Ученик: {child.full_name} ({child.class_name})\n"
            f"Ожидался через: {pickup.arrival_minutes} мин."
        )

        # Обновляем сообщение, убирая клавиатуру
        await callback.message.edit_text(new_text, reply_markup=None)
    finally:
        session.close()

    # Отправляем уведомление родителю
    farewell = ""
    today = date.today()
    weekday = today.weekday()  # 0 = Пн, 6 = Вс

    if weekday <= 3:  # Пн–Чт
        farewell = "Всего доброго! Ждём вас завтра."
    elif weekday == 4:  # Пт
        farewell = "Всего доброго! Ждём вас в понедельник."
    else:
        # Сб–Вс: отправляем только основное сообщение без фразы про завтра
        farewell = ""

    # Проверяем, есть ли у родителя несколько детей,
    # для которых сегодня оформлены заявки на выдачу.
    siblings_requests_today = 1
    try:
        session = SessionLocal()
        try:
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())
            siblings_requests_today = (
                session.query(PickupRequest)
                .filter(
                    PickupRequest.parent_id == parent.id,
                    PickupRequest.created_at >= today_start,
                    PickupRequest.created_at <= today_end,
                )
                .count()
            )
        finally:
            session.close()
    except Exception:
        siblings_requests_today = 1

    if siblings_requests_today > 1:
        base_text = "Ваши дети благополучно переданы. Спасибо!"
    else:
        base_text = "Ваш ребёнок благополучно передан. Спасибо!"

    if farewell:
        text_to_parent = f"{base_text}\n{farewell}"
    else:
        text_to_parent = base_text

    try:
        await callback.bot.send_message(parent.telegram_id, text_to_parent)
    except Exception:
        # Если не смогли уведомить родителя — не падаем.
        pass

    await callback.answer("Готово.")



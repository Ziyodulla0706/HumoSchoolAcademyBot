from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db.database import SessionLocal
from bot.db.models import User, Child, PickupRequest
from bot.config import ADMIN_IDS
from bot.states.admin_manage import AdminManageParentState
from aiogram.filters import Command

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def admin_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "Админ-панель:\n"
        "Отправьте номер телефона родителя (например +99890...) или его Telegram ID."
    )
    await state.set_state(AdminManageParentState.waiting_query)


@router.message(AdminManageParentState.waiting_query)
async def admin_find_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    q = message.text.strip()
    session = SessionLocal()
    try:
        parent = None

        # По Telegram ID
        if q.isdigit():
            parent = session.query(User).filter(User.telegram_id == int(q), User.role == "parent").first()

        # По телефону
        if not parent:
            parent = session.query(User).filter(User.phone == q, User.role == "parent").first()

        if not parent:
            await message.answer("Родитель не найден. Проверьте телефон/Telegram ID.")
            return

        await state.update_data(parent_id=parent.id)

        status = "ЗАБЛОКИРОВАН" if getattr(parent, "is_blocked", False) else "АКТИВЕН"

        await message.answer(
            f"Найден родитель:\n"
            f"ФИО: {parent.full_name}\n"
            f"Телефон: {parent.phone}\n"
            f"Telegram ID: {parent.telegram_id}\n"
            f"Статус: {status}\n\n"
            f"Команды:\n"
            f"1) /block — заблокировать\n"
            f"2) /unblock — разблокировать\n"
            f"3) /delete — удалить полностью (осторожно)"
        )
    finally:
        session.close()


@router.message(Command("block"))
async def admin_block_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    parent_id = data.get("parent_id")
    if not parent_id:
        await message.answer("Сначала найдите родителя через /admin.")
        return

    session = SessionLocal()
    try:
        parent = session.query(User).filter(User.id == parent_id, User.role == "parent").first()
        if not parent:
            await message.answer("Родитель не найден.")
            return

        parent.is_blocked = True
        session.commit()

        await message.answer("Готово: родитель заблокирован.")
    finally:
        session.close()


@router.message(Command("unblock"))
async def admin_unblock_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    parent_id = data.get("parent_id")
    if not parent_id:
        await message.answer("Сначала найдите родителя через /admin.")
        return

    session = SessionLocal()
    try:
        parent = session.query(User).filter(User.id == parent_id, User.role == "parent").first()
        if not parent:
            await message.answer("Родитель не найден.")
            return

        parent.is_blocked = False
        session.commit()

        await message.answer("Готово: родитель разблокирован.")
    finally:
        session.close()


@router.message(Command("delete"))
async def admin_delete_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    parent_id = data.get("parent_id")
    if not parent_id:
        await message.answer("Сначала найдите родителя через /admin.")
        return

    session = SessionLocal()
    try:
        parent = session.query(User).filter(User.id == parent_id, User.role == "parent").first()
        if not parent:
            await message.answer("Родитель не найден.")
            return

        # Удаляем связанные данные (hard delete)
        session.query(PickupRequest).filter(PickupRequest.parent_id == parent.id).delete()
        session.query(Child).filter(Child.parent_id == parent.id).delete()
        session.query(User).filter(User.id == parent.id).delete()
        session.commit()

        await message.answer("Готово: родитель и связанные данные удалены полностью.")
        await state.clear()
    finally:
        session.close()




@router.callback_query(lambda c: c.data.startswith("teacher_verify:"))
async def teacher_verify(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    user = session.query(User).filter(User.id == user_id).first()
    teacher = session.query(Teacher).filter(Teacher.user_id == user_id).first()

    if not user or not teacher:
        session.close()
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    user.role = "teacher"
    user.is_verified = True
    teacher.is_verified = True
    session.commit()

    teacher_tg = user.telegram_id
    session.close()

    await callback.message.edit_text("✅ Учитель подтверждён.")
    await callback.bot.send_message(
        teacher_tg,
        "✅ Ваша учётная запись учителя подтверждена.\nМеню учителя:",
        reply_markup=teacher_main_keyboard()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("teacher_reject:"))
async def teacher_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    user = session.query(User).filter(User.id == user_id).first()
    teacher = session.query(Teacher).filter(Teacher.user_id == user_id).first()

    if teacher:
        session.delete(teacher)
    if user:
        # можно оставить user как parent, либо удалить
        user.role = "parent"
        user.is_verified = False

    session.commit()
    session.close()

    await callback.message.edit_text("❌ Заявка учителя отклонена.")
    await callback.answer()

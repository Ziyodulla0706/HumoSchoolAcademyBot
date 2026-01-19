from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from bot.db.database import SessionLocal
from bot.db.models import User, Child, PickupRequest, Teacher, Grade, Attendance, Comment, Homework
from bot.config import ADMIN_IDS
from bot.states.admin_manage import AdminManageParentState

from bot.keyboards.teacher import teacher_main_keyboard
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------
# Админ-панель для родителей
# ---------------------------

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

    q = (message.text or "").strip()
    if not q:
        await message.answer("Пустой запрос. Отправьте телефон или Telegram ID.")
        return

    session = SessionLocal()
    try:
        parent = None

        # По Telegram ID
        if q.isdigit():
            parent = session.query(User).filter(
                User.telegram_id == int(q),
                User.role == "parent"
            ).first()

        # По телефону
        if not parent:
            parent = session.query(User).filter(
                User.phone == q,
                User.role == "parent"
            ).first()

        if not parent:
            await message.answer("Родитель не найден. Проверьте телефон/Telegram ID.")
            return

        await state.update_data(parent_id=parent.id)

        status = "ЗАБЛОКИРОВАН" if bool(getattr(parent, "is_blocked", False)) else "АКТИВЕН"
        
        # Подсчитываем количество детей
        children_count = session.query(Child).filter(Child.parent_id == parent.id).count()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔒 Заблокировать" if not parent.is_blocked else "🔓 Разблокировать",
                    callback_data=f"admin_toggle_block:{parent.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить родителя",
                    callback_data=f"admin_delete_parent:{parent.id}"
                )
            ]
        ])

        await message.answer(
            "Найден родитель:\n"
            f"ФИО: {parent.full_name}\n"
            f"Телефон: {parent.phone}\n"
            f"Telegram ID: {parent.telegram_id}\n"
            f"Статус: {status}\n"
            f"Детей: {children_count}\n\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
    finally:
        session.close()


@router.message(Command("block"))
async def admin_block_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    parent_id = (await state.get_data()).get("parent_id")
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

    parent_id = (await state.get_data()).get("parent_id")
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
async def admin_delete_parent_command(message: Message, state: FSMContext):
    """Команда удаления (для обратной совместимости)"""
    if not is_admin(message.from_user.id):
        return

    parent_id = (await state.get_data()).get("parent_id")
    if not parent_id:
        await message.answer("Сначала найдите родителя через /admin.")
        return

    await delete_parent_by_id(message, parent_id, bot=message.bot)
    await state.clear()


@router.callback_query(F.data.startswith("admin_delete_parent:"))
async def admin_delete_parent_callback(callback: CallbackQuery):
    """Удаление родителя через inline-кнопку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    parent_id = int(callback.data.split(":")[1])
    await delete_parent_by_id(callback.message, parent_id, callback=callback, bot=callback.bot)
    await callback.answer("Родитель удалён")


async def delete_parent_by_id(message_or_callback, parent_id, callback=None, bot=None):
    """Функция удаления родителя и всех связанных данных"""
    session = SessionLocal()
    try:
        parent = session.query(User).filter(User.id == parent_id, User.role == "parent").first()
        if not parent:
            text = "Родитель не найден."
            if callback:
                await callback.message.edit_text(text)
            else:
                await message_or_callback.answer(text)
            return

        parent_name = parent.full_name
        parent_tg_id = parent.telegram_id

        # Получаем ID всех детей родителя
        children = session.query(Child).filter(Child.parent_id == parent.id).all()
        child_ids = [child.id for child in children]

        # Удаляем все связанные данные
        if child_ids:
            # Удаляем оценки детей
            session.query(Grade).filter(Grade.child_id.in_(child_ids)).delete()
            # Удаляем посещаемость детей
            session.query(Attendance).filter(Attendance.child_id.in_(child_ids)).delete()
            # Удаляем комментарии к детям
            session.query(Comment).filter(Comment.child_id.in_(child_ids)).delete()

        # Удаляем заявки на вывоз
        session.query(PickupRequest).filter(PickupRequest.parent_id == parent.id).delete()
        # Удаляем детей
        session.query(Child).filter(Child.parent_id == parent.id).delete()
        # Удаляем самого родителя
        session.query(User).filter(User.id == parent.id).delete()
        
        session.commit()

        # Уведомляем родителя (если возможно)
        if bot:
            try:
                await bot.send_message(
                    parent_tg_id,
                    "❌ Ваш аккаунт был удалён администратором."
                )
            except:
                pass

        text = f"✅ Родитель '{parent_name}' и все связанные данные удалены полностью."
        if callback:
            await callback.message.edit_text(text)
        else:
            await message_or_callback.answer(text)
    finally:
        session.close()


@router.callback_query(F.data.startswith("admin_toggle_block:"))
async def admin_toggle_block(callback: CallbackQuery, state: FSMContext):
    """Блокировка/разблокировка родителя через inline-кнопку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    parent_id = int(callback.data.split(":")[1])
    
    session = SessionLocal()
    try:
        parent = session.query(User).filter(User.id == parent_id, User.role == "parent").first()
        if not parent:
            await callback.answer("Родитель не найден", show_alert=True)
            return

        parent.is_blocked = not parent.is_blocked
        session.commit()

        status_text = "заблокирован" if parent.is_blocked else "разблокирован"
        
        # Уведомляем родителя
        try:
            await callback.bot.send_message(
                parent.telegram_id,
                f"🔒 Ваш аккаунт {status_text} администратором."
            )
        except:
            pass

        await callback.answer(f"Родитель {status_text}")
        
        # Обновляем сообщение с новыми кнопками
        await state.update_data(parent_id=parent.id)
        status = "ЗАБЛОКИРОВАН" if parent.is_blocked else "АКТИВЕН"
        children_count = session.query(Child).filter(Child.parent_id == parent.id).count()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔒 Заблокировать" if not parent.is_blocked else "🔓 Разблокировать",
                    callback_data=f"admin_toggle_block:{parent.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить родителя",
                    callback_data=f"admin_delete_parent:{parent.id}"
                )
            ]
        ])

        await callback.message.edit_text(
            "Найден родитель:\n"
            f"ФИО: {parent.full_name}\n"
            f"Телефон: {parent.phone}\n"
            f"Telegram ID: {parent.telegram_id}\n"
            f"Статус: {status}\n"
            f"Детей: {children_count}\n\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
    finally:
        session.close()


# -----------------------------------
# Подтверждение / отклонение учителей
# -----------------------------------

@router.callback_query(F.data.startswith("teacher_verify:"))
async def teacher_verify(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user_id).first()

        if not user or not teacher:
            await callback.answer("Пользователь/учитель не найден", show_alert=True)
            return

        teacher.status = "approved"
        teacher.is_verified = True  # для обратной совместимости
        session.commit()

        teacher_tg = user.telegram_id
    finally:
        session.close()

    await callback.message.edit_text("✅ Учитель подтверждён.")
    await callback.bot.send_message(
        teacher_tg,
        "✅ Ваша учётная запись учителя подтверждена.\nМеню учителя:",
        reply_markup=teacher_main_keyboard()
    )
    await callback.answer()

    


@router.callback_query(F.data.startswith("teacher_reject:"))
async def teacher_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user_id).first()

        if teacher:
            session.delete(teacher)

        # Возвращаем роль назад в parent (или оставь как есть — на твой выбор)
        if user:
            user.role = "parent"

        session.commit()
    finally:
        session.close()

    await callback.message.edit_text("❌ Заявка учителя отклонена.")
    await callback.answer()

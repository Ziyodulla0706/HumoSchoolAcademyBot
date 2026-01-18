from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states.registration import (
    RegistrationState,
    AddChildState,
    PickupState,
    UpdatePhoneState,
    UpdateFullNameState,
    UpdateChildNameState
)

from bot.db.database import SessionLocal
from bot.db.models import User, Child, PickupRequest, Grade, Attendance, Homework, Comment, Subject
from datetime import date, datetime
from sqlalchemy import func

from bot.keyboards.parent import (
    parent_main_keyboard,
    children_inline_keyboard,
    time_inline_keyboard,
    children_edit_keyboard
)

from bot.keyboards.admin import guard_actions_keyboard
from bot.config import GUARD_CHANNEL_ID
import re

router = Router()


# =========================
# РЕГИСТРАЦИЯ РОДИТЕЛЯ
# =========================

@router.message(RegistrationState.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = " ".join((message.text or "").split())
    if len(full_name) < 3:
        await message.answer("Введите ФИО корректно.")
        return

    await state.update_data(full_name=full_name)
    await message.answer("Введите номер телефона\nв формате: +998901234567")
    await state.set_state(RegistrationState.waiting_phone)
    



PHONE_RE = re.compile(r"^\+998\d{9}$")  # строго под Узбекистан: +998XXXXXXXXX

@router.message(RegistrationState.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = (message.text or "").strip()

    # 1) Проверка номера (чтобы не записывался текст/мусор)
    if not PHONE_RE.match(phone):
        await message.answer(
            "Номер телефона некорректный.\n"
            "Введите в формате: +998901234567"
        )
        return

    session = SessionLocal()
    try:
        telegram_id = message.from_user.id

        # 2) Ищем пользователя по telegram_id
        user = session.query(User).filter(User.telegram_id == telegram_id).first()

        if user:
            # Обновляем существующего (НЕ создаём нового)
            user.full_name = data.get("full_name", user.full_name)
            user.phone = phone
            user.role = "parent"
            user.is_verified = False
        else:
            # Создаём только если реально нет
            user = User(
                telegram_id=telegram_id,
                full_name=data["full_name"],
                phone=phone,
                role="parent",
                is_verified=False
            )
            session.add(user)

        session.commit()
    finally:
        session.close()

    await message.answer(
        "Регистрация завершена.\n"
        "Ожидайте подтверждения администратора.",
        reply_markup=parent_main_keyboard()
    )
    await state.clear()



# =========================
# ДЕТИ
# =========================

@router.message(lambda m: m.text == "➕ Добавить ребёнка" or m.text == "Добавить ребёнка")
async def add_child_start(message: Message, state: FSMContext):
    await message.answer("Введите ФИО ребёнка:")
    await state.set_state(AddChildState.waiting_child_name)


@router.message(AddChildState.waiting_child_name)
async def process_child_name(message: Message, state: FSMContext):
    await state.update_data(child_name=message.text.strip())
    await message.answer("Введите класс ребёнка (например: 5А):")
    await state.set_state(AddChildState.waiting_class_name)


@router.message(AddChildState.waiting_class_name)
async def process_child_class(message: Message, state: FSMContext):
    data = await state.get_data()

    session = SessionLocal()
    try:
        parent = session.query(User).filter(
            User.telegram_id == message.from_user.id
        ).first()

        if not parent:
            await message.answer("Ошибка: пользователь не найден. Нажмите /start.")
            await state.clear()
            return

        child = Child(
            parent_id=parent.id,
            full_name=data["child_name"],
            class_name=message.text.strip()
        )

        session.add(child)
        session.commit()

        # сохраняем строку ДО закрытия сессии
        child_name = child.full_name

        await message.answer(
            f"Ребёнок «{child_name}» добавлен.",
            reply_markup=parent_main_keyboard()
        )
        await state.clear()
    finally:
        session.close()


@router.message(lambda m: m.text == "Мои дети")
async def list_children(message: Message):
    session = SessionLocal()
    try:
        parent = session.query(User).filter(
            User.telegram_id == message.from_user.id
        ).first()

        if not parent:
            await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
            return

        children = session.query(Child).filter(
            Child.parent_id == parent.id
        ).all()

        if not children:
            await message.answer("У вас пока нет добавленных детей.")
            return

        text = "Ваши дети:\n\n"
        for c in children:
            text += f"• {c.full_name} ({c.class_name})\n"

        await message.answer(text)
    finally:
        session.close()

@router.message(lambda m: m.text == "Изменить номер телефона")
async def update_phone_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите новый номер телефона\n"
        "в формате: +998901234567"
    )
    await state.set_state(UpdatePhoneState.waiting_phone)

@router.message(UpdatePhoneState.waiting_phone)
async def update_phone_process(message: Message, state: FSMContext):
    phone = (message.text or "").strip()

    if not PHONE_RE.match(phone):
        await message.answer(
            "Номер телефона некорректный.\n"
            "Введите в формате: +998901234567"
        )
        return

    session = SessionLocal()
    try:
        telegram_id = message.from_user.id
        user = session.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
            await state.clear()
            return

        user.phone = phone
        session.commit()
    finally:
        session.close()

    await message.answer(
        f"Номер обновлён: {phone}",
        reply_markup=parent_main_keyboard()
    )
    await state.clear()



# =========================
# Я ЕДУ ЗА РЕБЁНКОМ
# =========================

@router.message(lambda m: m.text == "Я еду за ребёнком")
async def pickup_start(message: Message, state: FSMContext):
    session = SessionLocal()
    try:
        parent = session.query(User).filter(
            User.telegram_id == message.from_user.id
        ).first()

        if not parent:
            await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
            return

        children = session.query(Child).filter(
            Child.parent_id == parent.id
        ).all()

        if not children:
            await message.answer("У вас нет добавленных детей.")
            return

        await message.answer(
            "Выберите ученика:",
            reply_markup=children_inline_keyboard(children)
        )
        await state.set_state(PickupState.choosing_child)
    finally:
        session.close()


@router.callback_query(
    PickupState.choosing_child,
    lambda c: c.data.startswith("pickup_child:")
)
async def pickup_choose_child(callback: CallbackQuery, state: FSMContext):
    child_id = int(callback.data.split(":")[1])
    await state.update_data(child_id=child_id)

    await callback.message.edit_text(
        "Через сколько минут вы приедете?",
        reply_markup=time_inline_keyboard()
    )
    await state.set_state(PickupState.choosing_time)


from datetime import datetime, timedelta
from sqlalchemy import and_

@router.callback_query(PickupState.choosing_time, lambda c: c.data.startswith("pickup_time:"))
async def pickup_choose_time(callback: CallbackQuery, state: FSMContext):
    minutes = int(callback.data.split(":")[1])
    data = await state.get_data()
    child_id = int(data["child_id"])

    session = SessionLocal()
    try:
        parent = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        
        if not parent:
            await callback.message.edit_text("Ошибка: пользователь не найден.")
            await state.clear()
            await callback.answer()
            return

        child = session.query(Child).filter(Child.id == child_id, Child.parent_id == parent.id).first()

        if not child:
            await callback.message.edit_text("Ошибка: ребёнок не найден или нет доступа.")
            await state.clear()
            await callback.answer()
            return

        # 1) Авто-просрочка старых активных заявок (например, старше 2 часов)
        expire_before = datetime.utcnow() - timedelta(hours=2)
        session.query(PickupRequest).filter(
            PickupRequest.status == "ACTIVE",
            PickupRequest.created_at < expire_before
        ).update({PickupRequest.status: "EXPIRED"}, synchronize_session=False)
        session.commit()

        # 2) Анти-дубли:
        # если уже есть ACTIVE заявка для этого ребёнка от этого родителя -> обновляем время, а не создаём новую
        existing = session.query(PickupRequest).filter(
            PickupRequest.parent_id == parent.id,
            PickupRequest.child_id == child.id,
            PickupRequest.status == "ACTIVE"
        ).order_by(PickupRequest.created_at.desc()).first()

        if existing:
            existing.arrival_minutes = minutes
            existing.updated_at = datetime.utcnow()
            session.commit()

            pickup_id = existing.id
            status_text = "Заявка обновлена (без дубля)."
        else:
            pickup = PickupRequest(
                parent_id=parent.id,
                child_id=child.id,
                arrival_minutes=minutes,
                status="ACTIVE"
            )
            session.add(pickup)
            session.commit()
            session.refresh(pickup)

            pickup_id = pickup.id
            status_text = "Заявка отправлена."

        # Данные, которые будем использовать после закрытия session
        child_name = child.full_name
        class_name = child.class_name
        parent_name = parent.full_name

    finally:
        session.close()

    # Сообщение родителю
    await callback.message.edit_text(
        f"{status_text}\n"
        f"Ребёнок: {child_name} ({class_name})\n"
        f"Прибытие через {minutes} мин."
    )

    # Сообщение в канал охраны
    if GUARD_CHANNEL_ID:
        await callback.bot.send_message(
            GUARD_CHANNEL_ID,
            f"📌 Выдача ученика\n"
            f"Родитель: {parent_name}\n"
            f"Ученик: {child_name} ({class_name})\n"
            f"Ожидается через: {minutes} мин.",
            reply_markup=guard_actions_keyboard(pickup_id)
        )

    await state.clear()
    await callback.answer()

# Обработчик "Я учитель" удалён - используйте "👨‍🏫 Я учитель" из меню выбора роли
# Обработчик находится в common.py


# =========================
# ПРОСМОТР ДАННЫХ РОДИТЕЛЕМ
# =========================

@router.message(lambda m: m.text == "📊 Оценки")
async def parent_view_grades(message: Message):
    """Просмотр оценок детей"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        children = session.query(Child).filter(Child.parent_id == user.id).all()
        if not children:
            await message.answer("У вас нет добавленных детей.")
            return

        text = "📊 Оценки ваших детей:\n\n"
        for child in children:
            grades = session.query(Grade).filter(Grade.child_id == child.id).order_by(Grade.date.desc()).limit(10).all()
            text += f"👤 {child.full_name} ({child.class_name}):\n"
            
            if grades:
                for grade in grades:
                    subject = session.query(Subject).filter(Subject.id == grade.subject_id).first()
                    text += f"  • {subject.name if subject else 'Не указан'}: {grade.grade} ({grade.date.strftime('%d.%m.%Y')})\n"
            else:
                text += "  Нет оценок\n"
            text += "\n"

        await message.answer(text)
    finally:
        session.close()


@router.message(lambda m: m.text == "📅 Посещаемость")
async def parent_view_attendance(message: Message):
    """Просмотр посещаемости детей"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        children = session.query(Child).filter(Child.parent_id == user.id).all()
        if not children:
            await message.answer("У вас нет добавленных детей.")
            return

        text = "📅 Посещаемость ваших детей:\n\n"
        today = date.today()
        
        for child in children:
            # Посещаемость за последние 7 дней
            attendance_list = session.query(Attendance).filter(
                Attendance.child_id == child.id,
                Attendance.date >= date(today.year, today.month, max(1, today.day - 7))
            ).order_by(Attendance.date.desc()).all()
            
            text += f"👤 {child.full_name} ({child.class_name}):\n"
            
            if attendance_list:
                for att in attendance_list:
                    status_text = {
                        "present": "✅ Присутствовал",
                        "absent": "❌ Отсутствовал",
                        "late": "⏰ Опоздал"
                    }.get(att.status, att.status)
                    text += f"  • {att.date.strftime('%d.%m.%Y')}: {status_text}\n"
            else:
                text += "  Нет данных\n"
            text += "\n"

        await message.answer(text)
    finally:
        session.close()


@router.message(lambda m: m.text == "📝 Домашние задания")
async def parent_view_homework(message: Message):
    """Просмотр домашних заданий"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        children = session.query(Child).filter(Child.parent_id == user.id).all()
        if not children:
            await message.answer("У вас нет добавленных детей.")
            return

        class_names = [c.class_name for c in children]
        homeworks = session.query(Homework).filter(
            Homework.class_name.in_(class_names),
            Homework.due_date >= date.today()
        ).order_by(Homework.due_date).all()

        text = "📝 Домашние задания:\n\n"
        
        if homeworks:
            for hw in homeworks:
                subject = session.query(Subject).filter(Subject.id == hw.subject_id).first()
                text += f"📚 {hw.class_name} - {subject.name if subject else 'Не указан'}\n"
                text += f"Сдать до: {hw.due_date.strftime('%d.%m.%Y')}\n"
                text += f"{hw.text}\n\n"
        else:
            text += "Нет активных домашних заданий."

        await message.answer(text)
    finally:
        session.close()


@router.message(lambda m: m.text == "💬 Комментарии учителей")
async def parent_view_comments(message: Message):
    """Просмотр комментариев учителей"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        children = session.query(Child).filter(Child.parent_id == user.id).all()
        if not children:
            await message.answer("У вас нет добавленных детей.")
            return

        child_ids = [c.id for c in children]
        comments = session.query(Comment).filter(
            Comment.child_id.in_(child_ids)
        ).order_by(Comment.created_at.desc()).limit(20).all()

        text = "💬 Комментарии учителей:\n\n"
        
        if comments:
            for comment in comments:
                child = session.query(Child).filter(Child.id == comment.child_id).first()
                type_map = {
                    "behavior": "Поведение",
                    "attendance": "Посещаемость",
                    "performance": "Успеваемость",
                }
                text += f"👤 {child.full_name if child else 'Неизвестно'}\n"
                text += f"Тип: {type_map.get(comment.comment_type, comment.comment_type)}\n"
                text += f"Дата: {comment.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"{comment.text}\n\n"
        else:
            text += "Нет комментариев."

        await message.answer(text)
    finally:
        session.close()


@router.message(lambda m: m.text == "🏆 Рейтинг ребёнка")
async def parent_view_rating(message: Message):
    """Просмотр рейтинга ребёнка (базовая версия)"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        children = session.query(Child).filter(Child.parent_id == user.id).all()
        if not children:
            await message.answer("У вас нет добавленных детей.")
            return

        text = "🏆 Рейтинг ваших детей:\n\n"
        
        for child in children:
            # Средний балл
            avg_grade = session.query(func.avg(Grade.grade)).filter(
                Grade.child_id == child.id
            ).scalar()
            
            # Посещаемость за месяц
            month_start = date.today().replace(day=1)
            total_days = session.query(Attendance).filter(
                Attendance.child_id == child.id,
                Attendance.date >= month_start
            ).count()
            present_days = session.query(Attendance).filter(
                Attendance.child_id == child.id,
                Attendance.date >= month_start,
                Attendance.status == "present"
            ).count()
            
            text += f"👤 {child.full_name} ({child.class_name}):\n"
            if avg_grade:
                text += f"  Средний балл: {avg_grade:.2f}\n"
            else:
                text += f"  Средний балл: нет оценок\n"
            
            if total_days > 0:
                attendance_percent = (present_days / total_days) * 100
                text += f"  Посещаемость: {present_days}/{total_days} ({attendance_percent:.1f}%)\n"
            else:
                text += f"  Посещаемость: нет данных\n"
            text += "\n"

        await message.answer(text)
    finally:
        session.close()


@router.message(lambda m: m.text == "⚙️ Настройки")
async def parent_settings(message: Message):
    """Настройки родителя"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить своё ФИО", callback_data="edit_parent_name")],
        [InlineKeyboardButton(text="✏️ Изменить ФИО ребёнка", callback_data="edit_child_name")],
        [InlineKeyboardButton(text="📱 Изменить номер телефона", callback_data="edit_phone")]
    ])
    
    await message.answer(
        "⚙️ Настройки:\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=keyboard
    )


# =========================
# ИЗМЕНЕНИЕ ФИО РОДИТЕЛЯ
# =========================

@router.callback_query(lambda c: c.data == "edit_parent_name")
async def edit_parent_name_start(callback: CallbackQuery, state: FSMContext):
    """Начало изменения ФИО родителя"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.answer("Сначала зарегистрируйтесь", show_alert=True)
            return

        await callback.message.edit_text(
            f"Текущее ФИО: {user.full_name}\n\n"
            "Введите новое ФИО:"
        )
        await state.set_state(UpdateFullNameState.waiting_full_name)
    finally:
        session.close()
    await callback.answer()


@router.message(UpdateFullNameState.waiting_full_name)
async def edit_parent_name_process(message: Message, state: FSMContext):
    """Обработка нового ФИО родителя"""
    new_full_name = " ".join((message.text or "").split())
    
    if len(new_full_name) < 3:
        await message.answer("ФИО слишком короткое. Введите корректное ФИО (минимум 3 символа):")
        return

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return

        old_name = user.full_name
        user.full_name = new_full_name
        session.commit()

        await message.answer(
            f"✅ ФИО успешно изменено:\n"
            f"Было: {old_name}\n"
            f"Стало: {new_full_name}",
            reply_markup=parent_main_keyboard()
        )
    finally:
        session.close()
    await state.clear()


# =========================
# ИЗМЕНЕНИЕ ФИО РЕБЁНКА
# =========================

@router.callback_query(lambda c: c.data == "edit_child_name")
async def edit_child_name_start(callback: CallbackQuery, state: FSMContext):
    """Начало изменения ФИО ребёнка"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.answer("Сначала зарегистрируйтесь", show_alert=True)
            return

        children = session.query(Child).filter(Child.parent_id == user.id).all()
        if not children:
            await callback.message.edit_text("У вас нет добавленных детей.")
            await callback.answer()
            return

        await callback.message.edit_text(
            "Выберите ребёнка, у которого хотите изменить ФИО:",
            reply_markup=children_edit_keyboard(children)
        )
        await state.set_state(UpdateChildNameState.choosing_child)
    finally:
        session.close()
    await callback.answer()


@router.callback_query(UpdateChildNameState.choosing_child, lambda c: c.data.startswith("edit_child:"))
async def edit_child_name_choose(callback: CallbackQuery, state: FSMContext):
    """Выбор ребёнка для изменения ФИО"""
    child_id = int(callback.data.split(":")[1])
    
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        child = session.query(Child).filter(
            Child.id == child_id,
            Child.parent_id == user.id
        ).first()

        if not child:
            await callback.message.edit_text("Ребёнок не найден.")
            await state.clear()
            return

        await state.update_data(child_id=child_id)
        await callback.message.edit_text(
            f"Текущее ФИО: {child.full_name}\n"
            f"Класс: {child.class_name}\n\n"
            "Введите новое ФИО:"
        )
        await state.set_state(UpdateChildNameState.waiting_new_name)
    finally:
        session.close()
    await callback.answer()


@router.message(UpdateChildNameState.waiting_new_name)
async def edit_child_name_process(message: Message, state: FSMContext):
    """Обработка нового ФИО ребёнка"""
    new_full_name = " ".join((message.text or "").split())
    
    if len(new_full_name) < 3:
        await message.answer("ФИО слишком короткое. Введите корректное ФИО (минимум 3 символа):")
        return

    data = await state.get_data()
    child_id = data.get("child_id")

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        child = session.query(Child).filter(
            Child.id == child_id,
            Child.parent_id == user.id
        ).first()

        if not child:
            await message.answer("Ошибка: ребёнок не найден.")
            await state.clear()
            return

        old_name = child.full_name
        child.full_name = new_full_name
        session.commit()

        await message.answer(
            f"✅ ФИО ребёнка успешно изменено:\n"
            f"Было: {old_name}\n"
            f"Стало: {new_full_name}\n"
            f"Класс: {child.class_name}",
            reply_markup=parent_main_keyboard()
        )
    finally:
        session.close()
    await state.clear()


# =========================
# ИЗМЕНЕНИЕ НОМЕРА ТЕЛЕФОНА (через настройки)
# =========================

@router.callback_query(lambda c: c.data == "edit_phone")
async def edit_phone_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения номера телефона через настройки"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.answer("Сначала зарегистрируйтесь", show_alert=True)
            return

        await callback.message.edit_text(
            f"Текущий номер: {user.phone or 'не указан'}\n\n"
            "Введите новый номер телефона\n"
            "в формате: +998901234567"
        )
        await state.set_state(UpdatePhoneState.waiting_phone)
    finally:
        session.close()
    await callback.answer()
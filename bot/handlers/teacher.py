from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import ADMIN_IDS
from bot.db.database import SessionLocal
from bot.db.models import User, Teacher, TeacherClass, Child, Subject, Grade, Comment, Homework
from bot.states.grade import GradeState
from bot.states.comment import CommentState
from bot.states.homework import HomeworkState
from datetime import date
from bot.states.teacher_registration import TeacherRegistrationState
from bot.states.teacher_message import TeacherMessageState
from bot.keyboards.teacher import (
    teacher_main_keyboard,
    teacher_classes_keyboard,
    teacher_message_type_keyboard
)
from bot.keyboards.admin import teacher_verify_keyboard


router = Router()


# Обработчик "👨‍🏫 Я учитель" находится в common.py для выбора роли
# Этот обработчик удалён, чтобы избежать конфликтов


@router.message(TeacherRegistrationState.waiting_full_name)
async def teacher_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=(message.text or "").strip())
    await message.answer(
        "Введите предмет, который вы преподаёте:\n"
        "Например: Математика, Русский язык, Физика и т.д."
    )
    await state.set_state(TeacherRegistrationState.waiting_subject)


@router.message(TeacherRegistrationState.waiting_subject)
async def teacher_subject(message: Message, state: FSMContext):
    subject_name = (message.text or "").strip()
    if not subject_name:
        await message.answer("Введите название предмета.")
        return

    await state.update_data(subject_name=subject_name)
    await message.answer(
        "Введите классы через запятую, которые вы ведёте.\n"
        "Пример: 1А, 1Б, 5В"
    )
    await state.set_state(TeacherRegistrationState.waiting_classes)


@router.message(TeacherRegistrationState.waiting_classes)
async def teacher_classes(message: Message, state: FSMContext):
    data = await state.get_data()
    full_name = (data.get("full_name") or "").strip()
    subject_name = (data.get("subject_name") or "").strip()

    classes_raw = (message.text or "").strip()
    classes = [c.strip().upper() for c in classes_raw.split(",") if c.strip()]

    if not full_name:
        await message.answer("ФИО пустое. Начните регистрацию заново.")
        await state.clear()
        return

    if not subject_name:
        await message.answer("Предмет не указан. Начните регистрацию заново.")
        await state.clear()
        return

    if not classes:
        await message.answer("Не нашёл классы. Введите ещё раз, пример: 1А, 5В")
        return

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь как родитель.")
            await state.clear()
            return

        # Обновляем ФИО
        user.full_name = full_name
        session.commit()

        # Находим или создаём предмет
        subject = session.query(Subject).filter(Subject.name == subject_name).first()
        if not subject:
            subject = Subject(name=subject_name)
            session.add(subject)
            session.commit()
            session.refresh(subject)

        # Находим или создаём учителя
        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            teacher = Teacher(
                user_id=user.id,
                subject_id=subject.id,
                status="pending",
                is_verified=False
            )
            session.add(teacher)
            session.commit()
            session.refresh(teacher)
        else:
            # Обновляем предмет, если заявка уже была
            teacher.subject_id = subject.id
            teacher.status = "pending"
            session.commit()

        # Обновляем классы
        session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).delete()
        session.commit()

        for cls in classes:
            session.add(TeacherClass(teacher_id=teacher.id, class_name=cls))
        session.commit()

        user_db_id = user.id
        teacher_name = user.full_name

    finally:
        session.close()

    # Уведомляем админов
    for admin_tg in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_tg,
                "🧑‍🏫 Новая заявка учителя\n"
                f"ФИО: {teacher_name}\n"
                f"Предмет: {subject_name}\n"
                f"Классы: {', '.join(classes)}\n"
                f"ID пользователя: {user_db_id}",
                reply_markup=teacher_verify_keyboard(user_db_id)
            )
        except Exception:
            pass

    await message.answer(
        "✅ Заявка отправлена администратору.\n"
        "Ожидайте подтверждения."
    )
    await state.clear()


@router.message(F.text == "🚪 Выйти из режима учителя")
async def teacher_exit(message: Message, state: FSMContext):
    """Выход из режима учителя"""
    await state.clear()
    from bot.keyboards.common import role_selection_keyboard
    from bot.config import ADMIN_IDS
    
    await message.answer(
        "Вы вышли из режима учителя.\n"
        "Выберите режим работы:",
        reply_markup=role_selection_keyboard(
            is_admin=message.from_user.id in ADMIN_IDS
        )
    )


@router.message(F.text == "📚 Мои классы")
async def teacher_my_classes(message: Message):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь как родитель.")
            return

        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher or not teacher.is_verified:
            await message.answer("Доступ только для подтверждённых учителей.")
            return

        classes = session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).all()
        if not classes:
            await message.answer("Классы не назначены.")
            return

        cls_list = [c.class_name for c in classes]
        await message.answer("Ваши классы:\n" + "\n".join([f"• {c}" for c in cls_list]))
    finally:
        session.close()


@router.message(F.text == "✉️ Сообщение родителям")
async def teacher_message_start(message: Message, state: FSMContext):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь как родитель.")
            return

        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher or not teacher.is_verified:
            await message.answer("Доступ только для подтверждённых учителей.")
            return

        classes = session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).all()
        if not classes:
            await message.answer("Вам не назначены классы. Обратитесь к администратору.")
            return

        cls_list = [c.class_name for c in classes]
        await message.answer("Выберите класс:", reply_markup=teacher_classes_keyboard(cls_list))
        await state.set_state(TeacherMessageState.choosing_class)
    finally:
        session.close()


@router.callback_query(TeacherMessageState.choosing_class, F.data.startswith("tmsg_class:"))
async def teacher_choose_class(callback: CallbackQuery, state: FSMContext):
    cls = callback.data.split(":", 1)[1].strip().upper()
    await state.update_data(class_name=cls)

    await callback.message.edit_text(
        f"Класс: {cls}\nВыберите тип сообщения:",
        reply_markup=teacher_message_type_keyboard()
    )
    await state.set_state(TeacherMessageState.choosing_type)
    await callback.answer()


@router.callback_query(TeacherMessageState.choosing_type, F.data == "tmsg_cancel")
async def teacher_message_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.callback_query(TeacherMessageState.choosing_type, F.data.startswith("tmsg_type:"))
async def teacher_choose_type(callback: CallbackQuery, state: FSMContext):
    msg_type = callback.data.split(":", 1)[1].strip()
    type_map = {
        "behavior": "Поведение",
        "attendance": "Посещаемость",
        "performance": "Успеваемость",
    }
    await state.update_data(message_type=msg_type)

    await callback.message.edit_text(
        f"Тип: {type_map.get(msg_type, msg_type)}\n\nВведите текст сообщения:"
    )
    await state.set_state(TeacherMessageState.entering_text)
    await callback.answer()


@router.message(TeacherMessageState.entering_text)
async def teacher_enter_text(message: Message, state: FSMContext):
    data = await state.get_data()
    class_name = (data.get("class_name") or "").strip().upper()
    msg_type = (data.get("message_type") or "").strip()
    text = (message.text or "").strip()

    if not class_name or not msg_type:
        await message.answer("Сессия сбилась. Нажмите «✉️ Сообщение родителям» заново.")
        await state.clear()
        return

    if not text:
        await message.answer("Текст пустой. Введите сообщение ещё раз.")
        return

    type_map = {
        "behavior": "Поведение",
        "attendance": "Посещаемость",
        "performance": "Успеваемость",
    }
    type_title = type_map.get(msg_type, msg_type)

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь как родитель.")
            await state.clear()
            return

        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher or not teacher.is_verified:
            await message.answer("Доступ только для подтверждённых учителей.")
            await state.clear()
            return

        allowed = session.query(TeacherClass).filter(
            TeacherClass.teacher_id == teacher.id,
            TeacherClass.class_name == class_name
        ).first()
        if not allowed:
            await message.answer("Этот класс не назначен вам.")
            await state.clear()
            return

        children = session.query(Child).filter(Child.class_name == class_name).all()
        if not children:
            await message.answer("В этом классе пока нет добавленных детей у родителей.")
            await state.clear()
            return

        parent_ids = list({c.parent_id for c in children})
        parents = session.query(User).filter(User.id.in_(parent_ids)).all()
    finally:
        session.close()

    delivered, failed = 0, 0
    for p in parents:
        try:
            await message.bot.send_message(
                p.telegram_id,
                "🏫 Сообщение от учителя\n"
                f"Класс: {class_name}\n"
                f"Тема: {type_title}\n\n"
                f"{text}"
            )
            delivered += 1
        except Exception:
            failed += 1

    await message.answer(f"Готово.\nОтправлено родителям: {delivered}\nНе доставлено: {failed}")
    await state.clear()


# =========================
# ОЦЕНКИ
# =========================

@router.message(F.text == "📝 Поставить оценку")
async def grade_start(message: Message, state: FSMContext):
    """Начало процесса выставления оценки"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь.")
            return

        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher or (teacher.status != "approved" and not teacher.is_verified):
            await message.answer("Доступ только для подтверждённых учителей.")
            return

        classes = session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).all()
        if not classes:
            await message.answer("Вам не назначены классы.")
            return

        class_list = [c.class_name for c in classes]
        await message.answer(
            "Выберите класс:",
            reply_markup=teacher_classes_keyboard(class_list)
        )
        await state.set_state(GradeState.choosing_class)
    finally:
        session.close()


@router.callback_query(GradeState.choosing_class, F.data.startswith("tmsg_class:"))
async def grade_choose_class(callback: CallbackQuery, state: FSMContext):
    """Выбор класса для оценки"""
    class_name = callback.data.split(":", 1)[1].strip().upper()
    await state.update_data(class_name=class_name)
    
    session = SessionLocal()
    try:
        children = session.query(Child).filter(Child.class_name == class_name).all()
        if not children:
            await callback.message.edit_text("В этом классе нет учеников.")
            await state.clear()
            return

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = []
        for child in children:
            keyboard.append([InlineKeyboardButton(
                text=child.full_name,
                callback_data=f"grade_student:{child.id}"
            )])

        await callback.message.edit_text(
            f"Класс: {class_name}\nВыберите ученика:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await state.set_state(GradeState.choosing_student)
    finally:
        session.close()
    await callback.answer()


@router.callback_query(GradeState.choosing_student, F.data.startswith("grade_student:"))
async def grade_choose_student(callback: CallbackQuery, state: FSMContext):
    """Выбор ученика для оценки"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(child_id=child_id)
    
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        
        if not teacher or not teacher.subject_id:
            await callback.message.edit_text("У вас не назначен предмет.")
            await state.clear()
            return

        subject = session.query(Subject).filter(Subject.id == teacher.subject_id).first()
        await callback.message.edit_text(
            f"Предмет: {subject.name if subject else 'Не указан'}\n"
            "Введите оценку (2, 3, 4, 5):"
        )
        await state.set_state(GradeState.entering_grade)
    finally:
        session.close()
    await callback.answer()


@router.message(GradeState.entering_grade)
async def grade_enter(message: Message, state: FSMContext):
    """Ввод оценки"""
    try:
        grade_value = int(message.text.strip())
        if grade_value not in [2, 3, 4, 5]:
            await message.answer("Оценка должна быть от 2 до 5. Введите ещё раз:")
            return
    except ValueError:
        await message.answer("Введите число от 2 до 5:")
        return

    data = await state.get_data()
    child_id = data.get("child_id")
    class_name = data.get("class_name")

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        child = session.query(Child).filter(Child.id == child_id).first()

        if not teacher or not child or not teacher.subject_id:
            await message.answer("Ошибка данных.")
            await state.clear()
            return

        # Создаём оценку
        grade = Grade(
            child_id=child_id,
            teacher_id=teacher.id,
            subject_id=teacher.subject_id,
            grade=grade_value,
            date=date.today()
        )
        session.add(grade)
        session.commit()

        # Уведомляем родителя
        parent = session.query(User).filter(User.id == child.parent_id).first()
        subject = session.query(Subject).filter(Subject.id == teacher.subject_id).first()
        
        if parent:
            try:
                await message.bot.send_message(
                    parent.telegram_id,
                    f"📝 Новая оценка\n\n"
                    f"Ученик: {child.full_name}\n"
                    f"Предмет: {subject.name if subject else 'Не указан'}\n"
                    f"Оценка: {grade_value}\n"
                    f"Дата: {date.today().strftime('%d.%m.%Y')}"
                )
            except:
                pass

        await message.answer(
            f"✅ Оценка {grade_value} выставлена ученику {child.full_name}",
            reply_markup=teacher_main_keyboard()
        )
    finally:
        session.close()
    await state.clear()


# =========================
# КОММЕНТАРИИ
# =========================

@router.message(F.text == "💬 Добавить комментарий ученику")
async def comment_start(message: Message, state: FSMContext):
    """Начало процесса добавления комментария"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь.")
            return

        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher or (teacher.status != "approved" and not teacher.is_verified):
            await message.answer("Доступ только для подтверждённых учителей.")
            return

        classes = session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).all()
        if not classes:
            await message.answer("Вам не назначены классы.")
            return

        class_list = [c.class_name for c in classes]
        await message.answer(
            "Выберите класс:",
            reply_markup=teacher_classes_keyboard(class_list)
        )
        await state.set_state(CommentState.choosing_class)
    finally:
        session.close()


@router.callback_query(CommentState.choosing_class, F.data.startswith("tmsg_class:"))
async def comment_choose_class(callback: CallbackQuery, state: FSMContext):
    """Выбор класса для комментария"""
    class_name = callback.data.split(":", 1)[1].strip().upper()
    await state.update_data(class_name=class_name)
    
    session = SessionLocal()
    try:
        children = session.query(Child).filter(Child.class_name == class_name).all()
        if not children:
            await callback.message.edit_text("В этом классе нет учеников.")
            await state.clear()
            return

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = []
        for child in children:
            keyboard.append([InlineKeyboardButton(
                text=child.full_name,
                callback_data=f"comment_student:{child.id}"
            )])

        await callback.message.edit_text(
            f"Класс: {class_name}\nВыберите ученика:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await state.set_state(CommentState.choosing_student)
    finally:
        session.close()
    await callback.answer()


@router.callback_query(CommentState.choosing_student, F.data.startswith("comment_student:"))
async def comment_choose_student(callback: CallbackQuery, state: FSMContext):
    """Выбор ученика для комментария"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(child_id=child_id)
    
    await callback.message.edit_text(
        "Выберите тип комментария:",
        reply_markup=teacher_message_type_keyboard()
    )
    await state.set_state(CommentState.choosing_type)
    await callback.answer()


@router.callback_query(CommentState.choosing_type, F.data.startswith("tmsg_type:"))
async def comment_choose_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа комментария"""
    comment_type = callback.data.split(":", 1)[1].strip()
    await state.update_data(comment_type=comment_type)
    
    type_map = {
        "behavior": "Поведение",
        "attendance": "Посещаемость",
        "performance": "Успеваемость",
    }
    
    await callback.message.edit_text(
        f"Тип: {type_map.get(comment_type, comment_type)}\n\nВведите текст комментария:"
    )
    await state.set_state(CommentState.entering_text)
    await callback.answer()


@router.message(CommentState.entering_text)
async def comment_enter_text(message: Message, state: FSMContext):
    """Ввод текста комментария"""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст пустой. Введите комментарий ещё раз:")
        return

    data = await state.get_data()
    child_id = data.get("child_id")
    comment_type = data.get("comment_type")

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        child = session.query(Child).filter(Child.id == child_id).first()

        if not teacher or not child:
            await message.answer("Ошибка данных.")
            await state.clear()
            return

        # Создаём комментарий
        comment = Comment(
            child_id=child_id,
            teacher_id=teacher.id,
            comment_type=comment_type,
            text=text
        )
        session.add(comment)
        session.commit()

        # Уведомляем родителя
        parent = session.query(User).filter(User.id == child.parent_id).first()
        type_map = {
            "behavior": "Поведение",
            "attendance": "Посещаемость",
            "performance": "Успеваемость",
        }
        
        if parent:
            try:
                await message.bot.send_message(
                    parent.telegram_id,
                    f"💬 Комментарий учителя\n\n"
                    f"Ученик: {child.full_name}\n"
                    f"Тип: {type_map.get(comment_type, comment_type)}\n\n"
                    f"{text}"
                )
            except:
                pass

        await message.answer(
            f"✅ Комментарий добавлен для {child.full_name}",
            reply_markup=teacher_main_keyboard()
        )
    finally:
        session.close()
    await state.clear()


# =========================
# ДОМАШНИЕ ЗАДАНИЯ
# =========================

@router.message(F.text == "📚 Домашнее задание")
async def homework_start(message: Message, state: FSMContext):
    """Начало процесса создания домашнего задания"""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь.")
            return

        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher or (teacher.status != "approved" and not teacher.is_verified):
            await message.answer("Доступ только для подтверждённых учителей.")
            return

        classes = session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).all()
        if not classes:
            await message.answer("Вам не назначены классы.")
            return

        class_list = [c.class_name for c in classes]
        await message.answer(
            "Выберите класс:",
            reply_markup=teacher_classes_keyboard(class_list)
        )
        await state.set_state(HomeworkState.choosing_class)
    finally:
        session.close()


@router.callback_query(HomeworkState.choosing_class, F.data.startswith("tmsg_class:"))
async def homework_choose_class(callback: CallbackQuery, state: FSMContext):
    """Выбор класса для ДЗ"""
    class_name = callback.data.split(":", 1)[1].strip().upper()
    await state.update_data(class_name=class_name)
    
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        
        if not teacher or not teacher.subject_id:
            await callback.message.edit_text("У вас не назначен предмет.")
            await state.clear()
            return

        subject = session.query(Subject).filter(Subject.id == teacher.subject_id).first()
        await callback.message.edit_text(
            f"Класс: {class_name}\n"
            f"Предмет: {subject.name if subject else 'Не указан'}\n\n"
            "Введите текст домашнего задания:"
        )
        await state.set_state(HomeworkState.entering_text)
    finally:
        session.close()
    await callback.answer()


@router.message(HomeworkState.entering_text)
async def homework_enter_text(message: Message, state: FSMContext):
    """Ввод текста ДЗ"""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст пустой. Введите домашнее задание ещё раз:")
        return

    await state.update_data(homework_text=text)
    await message.answer(
        "Введите дату сдачи в формате ДД.ММ.ГГГГ\n"
        "Например: 25.12.2024"
    )
    await state.set_state(HomeworkState.entering_due_date)


@router.message(HomeworkState.entering_due_date)
async def homework_enter_due_date(message: Message, state: FSMContext):
    """Ввод даты сдачи ДЗ"""
    try:
        from datetime import datetime
        due_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")
        return

    data = await state.get_data()
    class_name = data.get("class_name")
    text = data.get("homework_text")

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()

        if not teacher or not teacher.subject_id:
            await message.answer("Ошибка данных.")
            await state.clear()
            return

        # Создаём ДЗ
        homework = Homework(
            teacher_id=teacher.id,
            class_name=class_name,
            subject_id=teacher.subject_id,
            text=text,
            due_date=due_date
        )
        session.add(homework)
        session.commit()

        # Отправляем родителям
        children = session.query(Child).filter(Child.class_name == class_name).all()
        parent_ids = list({c.parent_id for c in children})
        parents = session.query(User).filter(User.id.in_(parent_ids)).all()
        
        subject = session.query(Subject).filter(Subject.id == teacher.subject_id).first()
        delivered = 0
        for p in parents:
            try:
                await message.bot.send_message(
                    p.telegram_id,
                    f"📚 Домашнее задание\n\n"
                    f"Класс: {class_name}\n"
                    f"Предмет: {subject.name if subject else 'Не указан'}\n"
                    f"Сдать до: {due_date.strftime('%d.%m.%Y')}\n\n"
                    f"{text}"
                )
                delivered += 1
            except:
                pass

        await message.answer(
            f"✅ Домашнее задание создано и отправлено родителям ({delivered} уведомлений)",
            reply_markup=teacher_main_keyboard()
        )
    finally:
        session.close()
    await state.clear()

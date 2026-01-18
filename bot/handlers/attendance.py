from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import date, datetime
from bot.db.database import SessionLocal
from bot.db.models import User, Teacher, TeacherClass, Child, Attendance
from bot.states.attendance import AttendanceState
from bot.keyboards.teacher import teacher_classes_keyboard

router = Router()


@router.message(F.text == "✅ Отметить посещаемость")
async def attendance_start(message: Message, state: FSMContext):
    """Начало процесса отметки посещаемости"""
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
            "Выберите класс для отметки посещаемости:",
            reply_markup=teacher_classes_keyboard(class_list)
        )
        await state.set_state(AttendanceState.choosing_class)
    finally:
        session.close()


@router.callback_query(AttendanceState.choosing_class, F.data.startswith("tmsg_class:"))
async def attendance_choose_class(callback: CallbackQuery, state: FSMContext):
    """Выбор класса для посещаемости"""
    class_name = callback.data.split(":", 1)[1].strip().upper()
    await state.update_data(class_name=class_name)
    
    # Получаем список учеников класса
    session = SessionLocal()
    try:
        children = session.query(Child).filter(Child.class_name == class_name).all()
        if not children:
            await callback.message.edit_text("В этом классе нет учеников.")
            await state.clear()
            return

        # Показываем список учеников с кнопками для отметки
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = []
        for child in children:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"✅ {child.full_name}",
                    callback_data=f"att_present:{child.id}"
                ),
                InlineKeyboardButton(
                    text=f"❌ {child.full_name}",
                    callback_data=f"att_absent:{child.id}"
                ),
                InlineKeyboardButton(
                    text=f"⏰ {child.full_name}",
                    callback_data=f"att_late:{child.id}"
                )
            ])

        await callback.message.edit_text(
            f"Класс: {class_name}\n"
            f"Дата: {date.today().strftime('%d.%m.%Y')}\n\n"
            "Отметьте посещаемость:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await state.set_state(AttendanceState.marking_attendance)
    finally:
        session.close()
    await callback.answer()


@router.callback_query(AttendanceState.marking_attendance, F.data.startswith("att_"))
async def mark_attendance(callback: CallbackQuery, state: FSMContext):
    """Отметка посещаемости ученика"""
    data = await state.get_data()
    class_name = data.get("class_name")
    
    parts = callback.data.split(":")
    status_map = {
        "att_present": "present",
        "att_absent": "absent",
        "att_late": "late"
    }
    
    status = status_map.get(parts[0])
    child_id = int(parts[1])
    
    if not status:
        await callback.answer("Ошибка", show_alert=True)
        return

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.telegram_id == callback.from_user.id).first()
        teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
        child = session.query(Child).filter(Child.id == child_id).first()

        if not teacher or not child:
            await callback.answer("Ошибка", show_alert=True)
            return

        # Проверяем, не отмечена ли уже посещаемость на сегодня
        today = date.today()
        existing = session.query(Attendance).filter(
            Attendance.child_id == child_id,
            Attendance.date == today
        ).first()

        if existing:
            existing.status = status
            existing.teacher_id = teacher.id
        else:
            attendance = Attendance(
                child_id=child_id,
                teacher_id=teacher.id,
                date=today,
                status=status
            )
            session.add(attendance)

        session.commit()

        # Уведомляем родителя
        parent = session.query(User).filter(User.id == child.parent_id).first()
        status_text_map = {
            "present": "присутствовал",
            "absent": "отсутствовал",
            "late": "опоздал"
        }
        status_text = status_text_map.get(status, status)
        
        if parent:
            try:
                await callback.bot.send_message(
                    parent.telegram_id,
                    f"📅 Посещаемость\n\n"
                    f"Ученик: {child.full_name}\n"
                    f"Класс: {child.class_name}\n"
                    f"Дата: {today.strftime('%d.%m.%Y')}\n"
                    f"Статус: {status_text}"
                )
            except:
                pass

        await callback.answer(f"Отмечено: {status_text}")
    finally:
        session.close()

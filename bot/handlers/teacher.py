from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.config import ADMIN_IDS
from bot.db.database import SessionLocal
from bot.db.models import User, Teacher, TeacherClass
from bot.states.teacher_registration import TeacherRegistrationState
from bot.keyboards.teacher import teacher_main_keyboard
from bot.keyboards.admin import teacher_verify_keyboard

router = Router()


@router.message(lambda m: m.text == "Я учитель")
async def teacher_start(message: Message, state: FSMContext):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    session.close()

    # Если пользователь уже есть и teacher подтвержден — сразу в меню учителя
    if user and user.role == "teacher" and user.is_verified:
        await message.answer("Меню учителя:", reply_markup=teacher_main_keyboard())
        return

    await message.answer("Введите ваше ФИО:")
    await state.set_state(TeacherRegistrationState.waiting_full_name)


@router.message(TeacherRegistrationState.waiting_full_name)
async def teacher_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "Введите классы через запятую.\n"
        "Пример: 1А, 1Б, 5В"
    )
    await state.set_state(TeacherRegistrationState.waiting_classes)


@router.message(TeacherRegistrationState.waiting_classes)
async def teacher_classes(message: Message, state: FSMContext):
    data = await state.get_data()
    full_name = data["full_name"]

    classes_raw = message.text.strip()
    classes = [c.strip().upper() for c in classes_raw.split(",") if c.strip()]

    if not classes:
        await message.answer("Не нашёл классы. Введите ещё раз, пример: 1А, 5В")
        return

    session = SessionLocal()

    # user upsert
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user:
        user = User(
            telegram_id=message.from_user.id,
            full_name=full_name,
            phone=None,
            role="teacher",
            is_verified=False
        )
        session.add(user)
        session.commit()
    else:
        user.full_name = full_name
        user.role = "teacher"
        user.is_verified = False
        session.commit()

    # teacher profile upsert
    teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
    if not teacher:
        teacher = Teacher(user_id=user.id, is_verified=False)
        session.add(teacher)
        session.commit()

    # очистим старые классы и запишем новые
    session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).delete()
    session.commit()

    for cls in classes:
        session.add(TeacherClass(teacher_id=teacher.id, class_name=cls))
    session.commit()

    user_id = user.id
    teacher_name = user.full_name
    session.close()

    # Уведомим админов
    for admin_tg in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_tg,
                f"🧑‍🏫 Новая заявка учителя\n"
                f"ФИО: {teacher_name}\n"
                f"Классы: {', '.join(classes)}\n"
                f"ID пользователя: {user_id}",
                reply_markup=teacher_verify_keyboard(user_id)
            )
        except Exception:
            pass

    await message.answer(
        "Заявка отправлена администратору.\n"
        "Ожидайте подтверждения."
    )
    await state.clear()



@router.message(lambda m: m.text == "📚 Мои классы")
async def teacher_my_classes(message: Message):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or user.role != "teacher" or not user.is_verified:
        session.close()
        await message.answer("У вас нет доступа к меню учителя.")
        return

    teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
    classes = session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).all()
    session.close()

    if not classes:
        await message.answer("Классы не назначены.")
        return

    cls_list = [c.class_name for c in classes]
    await message.answer("Ваши классы:\n" + "\n".join([f"• {c}" for c in cls_list]))


@router.message(lambda m: m.text == "✉️ Сообщение родителям")
async def teacher_message_start(message: Message, state: FSMContext):
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()

    if not user or user.role != "teacher" or not user.is_verified:
        session.close()
        await message.answer("Доступ только для подтверждённых учителей.")
        return

    teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()
    classes = session.query(TeacherClass).filter(TeacherClass.teacher_id == teacher.id).all()
    session.close()

    if not classes:
        await message.answer("Вам не назначены классы. Обратитесь к администратору.")
        return

    cls_list = [c.class_name for c in classes]
    await message.answer(
        "Выберите класс:",
        reply_markup=teacher_classes_keyboard(cls_list)
    )
    await state.set_state(TeacherMessageState.choosing_class)


@router.callback_query(TeacherMessageState.choosing_class, lambda c: c.data.startswith("tmsg_class:"))
async def teacher_choose_class(callback: CallbackQuery, state: FSMContext):
    cls = callback.data.split(":", 1)[1].strip().upper()
    await state.update_data(class_name=cls)

    await callback.message.edit_text(
        f"Класс: {cls}\nВыберите тип сообщения:",
        reply_markup=teacher_message_type_keyboard()
    )
    await state.set_state(TeacherMessageState.choosing_type)
    await callback.answer()


@router.callback_query(TeacherMessageState.choosing_type, lambda c: c.data.startswith("tmsg_type:"))
async def teacher_choose_type(callback: CallbackQuery, state: FSMContext):
    msg_type = callback.data.split(":", 1)[1]

    # человекочитаемое название
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


@router.callback_query(TeacherMessageState.choosing_type, lambda c: c.data == "tmsg_cancel")
async def teacher_message_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.message(TeacherMessageState.entering_text)
async def teacher_enter_text(message: Message, state: FSMContext):
    data = await state.get_data()
    class_name = data.get("class_name")
    msg_type = data.get("message_type")

    type_map = {
        "behavior": "Поведение",
        "attendance": "Посещаемость",
        "performance": "Успеваемость",
    }
    type_title = type_map.get(msg_type, msg_type)

    text = message.text.strip()

    session = SessionLocal()

    # проверка учителя
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or user.role != "teacher" or not user.is_verified:
        session.close()
        await message.answer("Доступ только для подтверждённых учителей.")
        await state.clear()
        return

    teacher = session.query(Teacher).filter(Teacher.user_id == user.id).first()

    # проверим, что класс действительно назначен этому учителю
    allowed = session.query(TeacherClass).filter(
        TeacherClass.teacher_id == teacher.id,
        TeacherClass.class_name == class_name
    ).first()

    if not allowed:
        session.close()
        await message.answer("Этот класс не назначен вам.")
        await state.clear()
        return

    # найдём всех детей этого класса и их родителей
    children = session.query(Child).filter(Child.class_name == class_name).all()
    if not children:
        session.close()
        await message.answer("В этом классе пока нет добавленных детей у родителей.")
        await state.clear()
        return

    parent_ids = list({c.parent_id for c in children})
    parents = session.query(User).filter(User.id.in_(parent_ids)).all()
    session.close()

    delivered = 0
    failed = 0

    # рассылка
    for p in parents:
        try:
            await message.bot.send_message(
                p.telegram_id,
                f"🏫 Сообщение от учителя\n"
                f"Класс: {class_name}\n"
                f"Тема: {type_title}\n\n"
                f"{text}"
            )
            delivered += 1
        except Exception:
            failed += 1

    await message.answer(
        f"Готово.\n"
        f"Отправлено родителям: {delivered}\n"
        f"Не доставлено: {failed}"
    )
    await state.clear()

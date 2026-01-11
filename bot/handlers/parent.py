from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states.registration import (
    RegistrationState,
    AddChildState,
    PickupState,
    UpdatePhoneState

)

from bot.db.database import SessionLocal
from bot.db.models import User, Child, PickupRequest

from bot.keyboards.parent import (
    parent_main_keyboard,
    children_inline_keyboard,
    time_inline_keyboard
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

@router.message(lambda m: m.text == "Добавить ребёнка")
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
    parent = session.query(User).filter(
        User.telegram_id == message.from_user.id
    ).first()

    child = Child(
        parent_id=parent.id,
        full_name=data["child_name"],
        class_name=message.text.strip()
    )

    session.add(child)
    session.commit()

    # сохраняем строку ДО закрытия сессии
    child_name = child.full_name
    session.close()

    await message.answer(
        f"Ребёнок «{child_name}» добавлен.",
        reply_markup=parent_main_keyboard()
    )
    await state.clear()


@router.message(lambda m: m.text == "Мои дети")
async def list_children(message: Message):
    session = SessionLocal()
    parent = session.query(User).filter(
        User.telegram_id == message.from_user.id
    ).first()

    children = session.query(Child).filter(
        Child.parent_id == parent.id
    ).all()

    if not children:
        await message.answer("У вас пока нет добавленных детей.")
        session.close()
        return

    text = "Ваши дети:\n\n"
    for c in children:
        text += f"• {c.full_name} ({c.class_name})\n"

    session.close()
    await message.answer(text)

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
    parent = session.query(User).filter(
        User.telegram_id == message.from_user.id
    ).first()

    children = session.query(Child).filter(
        Child.parent_id == parent.id
    ).all()
    session.close()

    if not children:
        await message.answer("У вас нет добавленных детей.")
        return

    await message.answer(
        "Выберите ученика:",
        reply_markup=children_inline_keyboard(children)
    )
    await state.set_state(PickupState.choosing_child)


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
        child = session.query(Child).filter(Child.id == child_id, Child.parent_id == parent.id).first()

        if not parent or not child:
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

@router.message(lambda m: m.text == "Я учитель")
async def switch_to_teacher(message: Message):
    session = SessionLocal()

    user = session.query(User).filter(
        User.telegram_id == message.from_user.id
    ).first()

    if not user:
        session.close()
        await message.answer("Сначала нажмите /start и пройдите регистрацию.")
        return

    # переключаем роль
    user.role = "teacher"
    user.is_verified = False
    session.commit()
    session.close()

    await message.answer(
        "Вы переключились в режим учителя.\n"
        "Ожидайте подтверждения администратора.\n\n"
        "После подтверждения используйте команду /teacher."
    )
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from bot.db.database import SessionLocal
from bot.db.models import User, Teacher
from bot.config import ADMIN_IDS
from bot.keyboards.common import role_selection_keyboard
from bot.keyboards.parent import parent_main_keyboard
from bot.keyboards.teacher import teacher_main_keyboard

router = Router()


def is_admin_user(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    session = SessionLocal()
    try:
        user = session.query(User).filter(
            User.telegram_id == message.from_user.id
        ).first()

        # Новый пользователь — показываем выбор роли
        if not user:
            await message.answer(
                "👋 Добро пожаловать в школьный бот!\n\n"
                "Выберите вашу роль:",
                reply_markup=role_selection_keyboard(
                    is_admin=is_admin_user(message.from_user.id)
                )
            )
            return

        # Заблокированный пользователь
        if user.is_blocked:
            await message.answer(
                "❌ Ваш аккаунт заблокирован. Обратитесь к администратору."
            )
            return

        # Есть, но не подтверждён
        if not user.is_verified:
            await message.answer(
                "⏳ Ваша регистрация ожидает подтверждения администратора."
            )
            return

        # ✅ Подтверждённый пользователь — показываем выбор роли
        admin_access = is_admin_user(message.from_user.id)
        await message.answer(
            f"👋 Здравствуйте, {user.full_name}!\n\n"
            "Выберите режим работы:",
            reply_markup=role_selection_keyboard(is_admin=admin_access)
        )
    finally:
        session.close()


@router.message(F.text == "👨‍👩‍👧 Я родитель")
async def parent_role_handler(message: Message, state: FSMContext):
    """Обработчик выбора роли родителя"""
    from bot.states.registration import RegistrationState
    
    session = SessionLocal()
    try:
        user = session.query(User).filter(
            User.telegram_id == message.from_user.id
        ).first()

        # Если пользователя нет - начинаем регистрацию
        if not user:
            await message.answer(
                "👨‍👩‍👧 Вы выбрали режим родителя.\n\n"
                "Для работы в этом режиме необходимо пройти регистрацию.\n"
                "Введите ваше ФИО:"
            )
            await state.set_state(RegistrationState.waiting_full_name)
            return

        if user.is_blocked:
            await message.answer("❌ Ваш аккаунт заблокирован.")
            return

        if not user.is_verified:
            await message.answer("⏳ Ваша регистрация ожидает подтверждения администратора.")
            return

        # Переключаем роль на parent
        user.role = "parent"
        session.commit()

        await message.answer(
            "👨‍👩‍👧 Режим родителя\n\n"
            "Выберите действие:",
            reply_markup=parent_main_keyboard()
        )
    finally:
        session.close()


@router.message(F.text == "👨‍🏫 Я учитель")
async def teacher_role_handler(message: Message, state: FSMContext):
    """Обработчик выбора роли учителя"""
    from bot.states.teacher_registration import TeacherRegistrationState
    from bot.states.registration import RegistrationState
    
    session = SessionLocal()
    try:
        user = session.query(User).filter(
            User.telegram_id == message.from_user.id
        ).first()

        # Если пользователя нет - сначала нужно зарегистрироваться как родитель
        if not user:
            await message.answer(
                "👨‍🏫 Вы выбрали режим учителя.\n\n"
                "Сначала необходимо зарегистрироваться как родитель.\n"
                "Введите ваше ФИО:"
            )
            await state.set_state(RegistrationState.waiting_full_name)
            return

        if user.is_blocked:
            await message.answer("❌ Ваш аккаунт заблокирован.")
            return

        if not user.is_verified:
            await message.answer("⏳ Ваша регистрация ожидает подтверждения администратора.")
            return

        # Проверяем, есть ли учитель в таблице teachers
        teacher = session.query(Teacher).filter(
            Teacher.user_id == user.id
        ).first()

        if not teacher:
            # Нет учителя — нужно зарегистрироваться как учитель
            await message.answer(
                "👨‍🏫 Вы выбрали режим учителя.\n\n"
                "Для работы в этом режиме необходимо пройти регистрацию учителя.\n"
                "Введите ваше ФИО:"
            )
            await state.set_state(TeacherRegistrationState.waiting_full_name)
            return

        # Проверяем статус учителя
        if teacher.status != "approved" and not teacher.is_verified:
            await message.answer(
                "⏳ Ваша заявка учителя ожидает подтверждения администратора."
            )
            return

        # Учитель подтверждён — показываем меню
        await message.answer(
            f"👨‍🏫 Режим учителя\n\n"
            f"Здравствуйте, {user.full_name}!\n"
            "Выберите действие:",
            reply_markup=teacher_main_keyboard()
        )
    finally:
        session.close()


@router.message(F.text == "⚙️ Я администратор")
async def admin_role_handler(message: Message, state: FSMContext):
    """Обработчик выбора роли администратора"""
    from bot.states.registration import RegistrationState
    
    if not is_admin_user(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return

    session = SessionLocal()
    try:
        user = session.query(User).filter(
            User.telegram_id == message.from_user.id
        ).first()

        # Если пользователя нет - начинаем регистрацию
        if not user:
            await message.answer(
                "⚙️ Вы выбрали режим администратора.\n\n"
                "Сначала необходимо пройти регистрацию.\n"
                "Введите ваше ФИО:"
            )
            await state.set_state(RegistrationState.waiting_full_name)
            return

        user.role = "admin"
        session.commit()

        await message.answer(
            "⚙️ Режим администратора\n\n"
            "Используйте команды:\n"
            "/admin - управление родителями\n"
            "/approve - подтверждение заявок\n"
            "/teacher_approve - подтверждение учителей"
        )
    finally:
        session.close()


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    """Сброс состояния FSM"""
    await state.clear()
    await message.answer("Состояние сброшено. Используйте /start для начала работы.")


from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from bot.db.database import SessionLocal
from bot.db.models import User
from bot.states.registration import RegistrationState
from bot.keyboards.parent import parent_main_keyboard

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    session = SessionLocal()

    user = session.query(User).filter(
        User.telegram_id == message.from_user.id
    ).first()

    # Новый пользователь — регистрация
    if not user:
        await message.answer(
            "Добро пожаловать!\n\n"
            "Для регистрации введите ваше ФИО:"
        )
        await state.set_state(RegistrationState.waiting_full_name)
        session.close()
        return

    # Есть, но не подтверждён
    if not user.is_verified:
        await message.answer(
            "Ваша регистрация ожидает подтверждения администратора."
        )
        session.close()
        return

    # ✅ Подтверждённый пользователь — меню
    await message.answer(
        f"Здравствуйте, {user.full_name}.\n"
        "Выберите действие:",
        reply_markup=parent_main_keyboard()
    )

    session.close()


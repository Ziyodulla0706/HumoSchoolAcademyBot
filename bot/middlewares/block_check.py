from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from bot.db.database import SessionLocal
from bot.db.models import User
from bot.config import ADMIN_IDS


class BlockCheckMiddleware(BaseMiddleware):
    """Middleware для проверки блокировки пользователя перед каждым действием"""
    
    # Команды, которые должны работать даже для заблокированных пользователей
    ALLOWED_COMMANDS = ["/start", "/cancel"]
    
    # Callback-данные от охраны и админских действий (не требуют проверки блокировки для админов)
    ADMIN_CALLBACKS = ["pickup_done:", "approve_user:", "admin_", "teacher_verify:", "teacher_reject:"]
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        # Админы не проверяются на блокировку (для любых команд и callback)
        if user_id in ADMIN_IDS:
            return await handler(event, data)
        
        # Пропускаем callback от охраны (pickup_done) - это может быть охранник, не админ
        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            if any(callback_data.startswith(prefix) for prefix in self.ADMIN_CALLBACKS):
                # Эти callback требуют отдельной проверки прав внутри обработчиков
                return await handler(event, data)
        
        # Пропускаем определенные команды, чтобы заблокированные могли видеть сообщение о блокировке
        if isinstance(event, Message):
            text = (event.text or "").strip()
            # Проверяем разрешенные команды
            if any(text.startswith(cmd) for cmd in self.ALLOWED_COMMANDS):
                return await handler(event, data)
        
        # Проверяем блокировку в БД
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.telegram_id == user_id).first()
            
            if user and user.is_blocked:
                # Пользователь заблокирован - отправляем сообщение и не выполняем обработчик
                if isinstance(event, CallbackQuery):
                    await event.answer(
                        "❌ Ваш аккаунт заблокирован администратором.",
                        show_alert=True
                    )
                    # Также отправляем сообщение в чат
                    try:
                        await event.message.answer(
                            "❌ Ваш аккаунт заблокирован администратором.\n"
                            "Обратитесь к администратору для получения дополнительной информации."
                        )
                    except:
                        pass
                else:  # Message
                    await event.answer(
                        "❌ Ваш аккаунт заблокирован администратором.\n"
                        "Обратитесь к администратору для получения дополнительной информации."
                    )
                return  # Прерываем выполнение обработчика
        finally:
            session.close()
        
        # Пользователь не заблокирован - продолжаем обработку
        return await handler(event, data)

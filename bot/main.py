import asyncio
import sqlite3

from aiogram import Bot, Dispatcher

from bot.config import BOT_TOKEN
from bot.db.database import engine, Base
from bot.handlers import parent, admin, common,  admin_manage


def ensure_sqlite_schema():
    """
    Минимальная "миграция" для SQLite без Alembic:
    - добавляем users.is_blocked (если ещё нет)
    Остальные таблицы создаются через Base.metadata.create_all().
    """
    # engine.url.database для sqlite:///./school.db обычно даёт относительный путь.
    # Поэтому используем ровно тот путь, который в DB_URL: ./school.db
    db_path = "school.db"

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # Проверяем наличие колонки is_blocked
        cur.execute("PRAGMA table_info(users);")
        cols = [row[1] for row in cur.fetchall()]  # row[1] = column name

        if "is_blocked" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0;")
            conn.commit()

    finally:
        conn.close()


async def main():
    # 1) Миграция/проверка схемы SQLite (без удаления базы)
    ensure_sqlite_schema()

    # 2) Создание отсутствующих таблиц (teachers, teacher_classes, etc.)
    Base.metadata.create_all(bind=engine)

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(common.router)
    dp.include_router(parent.router)
    dp.include_router(admin.router)
    dp.include_router(admin_manage.router)
    

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

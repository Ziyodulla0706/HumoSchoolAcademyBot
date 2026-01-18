import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher

from bot.config import BOT_TOKEN
from bot.db.database import engine, Base
from bot.handlers import parent, admin, common, admin_manage, teacher, attendance


# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
# -----------------------------------------


def ensure_sqlite_schema():
    """
    Минимальная миграция SQLite без Alembic:
    - добавляет users.is_blocked
    - добавляет pickup_requests.updated_at
    """
    db_path = "school.db"

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # users.is_blocked
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if cur.fetchone() is not None:
            cur.execute("PRAGMA table_info(users);")
            cols = [row[1] for row in cur.fetchall()]
            if "is_blocked" not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0;")
                conn.commit()
                logging.info("Column users.is_blocked added")

        # pickup_requests.updated_at
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pickup_requests';")
        if cur.fetchone() is not None:
            cur.execute("PRAGMA table_info(pickup_requests);")
            cols = [row[1] for row in cur.fetchall()]
            if "updated_at" not in cols:
                cur.execute("ALTER TABLE pickup_requests ADD COLUMN updated_at DATETIME;")
                conn.commit()
                logging.info("Column pickup_requests.updated_at added")

    finally:
        conn.close()




async def main():
    logging.info("Bot starting...")

    try:
        # 1) Создание всех таблиц из SQLAlchemy моделей
        Base.metadata.create_all(bind=engine)
        logging.info("DB create_all done")

        # 2) Мини-миграция SQLite
        ensure_sqlite_schema()
        logging.info("SQLite schema ensured")

        # 3) Проверка токена
        logging.info("BOT_TOKEN present: %s", bool(BOT_TOKEN))
        if not BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN is empty")

        # 4) Инициализация бота
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher()

        dp.include_router(common.router)
        dp.include_router(parent.router)
        dp.include_router(admin.router)
        dp.include_router(admin_manage.router)
        dp.include_router(teacher.router)
        dp.include_router(attendance.router)

        logging.info("Starting polling...")
        await dp.start_polling(bot)

    except Exception:
        logging.exception("Fatal error in main()")
        raise


if __name__ == "__main__":
    asyncio.run(main())


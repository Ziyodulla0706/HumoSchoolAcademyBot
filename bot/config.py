import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = [
    48820538,  # мама
    3565880,   # завуч
    800060636  # я
]
GUARD_CHANNEL_ID = -1003679118381

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Проверь файл .env")

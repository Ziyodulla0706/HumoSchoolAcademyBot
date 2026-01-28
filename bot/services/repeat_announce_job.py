from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from bot.db.database import SessionLocal
from bot.db.models import PickupRequest
from bot.services import PAAdapter, is_auto_voice_active


logger = logging.getLogger(__name__)


ANNOUNCE_INTERVAL_MINUTES = 4
POLL_INTERVAL_SECONDS = 20


async def _process_due_announcements(pa: PAAdapter) -> None:
    """
    Находит заявки, для которых пора повторить озвучку, и выполняет её.

    Защита от гонок реализована на уровне условия WHERE:
    - повторяем только заявки, у которых status != 'HANDED_OVER'
      и next_announce_at <= now.
    """
    now = datetime.utcnow()

    session = SessionLocal()
    try:
        # Берём только те заявки, которым уже назначено время следующей озвучки
        # и которые ещё не были закрыты.
        candidates = (
            session.query(PickupRequest)
            .filter(
                PickupRequest.status != "HANDED_OVER",
                PickupRequest.next_announce_at != None,  # noqa: E711
                PickupRequest.next_announce_at <= now,
            )
            .all()
        )

        for req in candidates:
            # Повторную озвучку делаем только если режим активен.
            if not is_auto_voice_active():
                continue

            text = (
                f"Просьба вызвать ученика {req.child_id} "
                f"к выходу. Родитель прибудет через {req.arrival_minutes} минут."
            )

            ok = await pa.announce(text)
            if not ok:
                # В случае ошибки просто логируем и попробуем ещё раз
                # на следующей итерации.
                logger.warning(
                    "Не удалось выполнить повторную озвучку (pickup_id=%s)", req.id
                )
                continue

            req.last_announce_at = now
            req.next_announce_at = now + timedelta(minutes=ANNOUNCE_INTERVAL_MINUTES)
            req.announce_count = (req.announce_count or 0) + 1
            # Если ранее был PENDING, переводим в ANNOUNCED
            if req.status == "PENDING":
                req.status = "ANNOUNCED"

        session.commit()
    except Exception:
        logger.exception("Ошибка в обработке повторных озвучек")
        session.rollback()
    finally:
        session.close()


async def start_repeat_announce_job(pa: PAAdapter) -> None:
    """
    Фоновая задача, которую запускаем при старте бота.

    Каждые POLL_INTERVAL_SECONDS секунд:
    - проверяем, активен ли режим автоголоса;
    - ищем заявки, для которых наступило время next_announce_at;
    - выполняем повторные озвучки.
    """
    logger.info(
        "Запуск фоновой задачи повторных озвучек (interval=%s сек.)",
        POLL_INTERVAL_SECONDS,
    )
    while True:
        try:
            if is_auto_voice_active():
                await _process_due_announcements(pa)
        except Exception:
            logger.exception("Ошибка в repeat_announce_job.loop")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


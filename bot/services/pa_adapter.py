from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)


class PAAdapter:
    """
    Адаптер системы озвучки (PA – Public Address).

    Сейчас это заглушка, которая просто логирует текст объявления.
    В будущем здесь можно реализовать интеграцию с SIP/AUX/IP‑громкоговорителем
    без изменений в хэндлерах.
    """

    async def announce(self, text: str, zone: Optional[str] = None) -> bool:
        """
        Озвучивает текст в заданной зоне.

        Возвращает:
            True  - если «озвучка» прошла успешно (для заглушки всегда True)
            False - при ошибке
        """
        try:
            if zone:
                logger.info("[PA][zone=%s] ANNOUNCE: %s", zone, text)
            else:
                logger.info("[PA] ANNOUNCE: %s", text)
            # Здесь в будущем можно разместить реальный вызов SIP/IP‑системы.
            return True
        except Exception:
            logger.exception("Ошибка при выполнении голосового объявления")
            return False


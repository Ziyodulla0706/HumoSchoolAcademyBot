from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Optional

import logging


logger = logging.getLogger(__name__)


class VoiceMode(str, Enum):
    AUTO = "AUTO"
    FORCE_ON = "FORCE_ON"
    FORCE_OFF = "FORCE_OFF"


@dataclass
class VoiceSettingsState:
    mode: VoiceMode = VoiceMode.AUTO


_state = VoiceSettingsState()


def set_voice_mode(mode: VoiceMode) -> None:
    """Устанавливает ручной режим работы озвучки."""
    logger.info("VoiceMode changed to %s", mode)
    _state.mode = mode


def get_voice_mode() -> VoiceMode:
    return _state.mode


def _is_in_schedule(now: Optional[datetime] = None) -> bool:
    """
    Проверка попадания во временное окно.

    По ТЗ:
    - Режим Авто считается активным, если время в диапазоне 14:00–19:00
      (Asia/Tashkent). Здесь предполагаем, что локальное время сервера уже
      настроено на этот часовой пояс.
    """
    if now is None:
        now = datetime.now()

    start = time(14, 0)
    end = time(19, 0)
    return start <= now.time() <= end


def is_auto_voice_active(now: Optional[datetime] = None) -> bool:
    """
    Итоговая функция из ТЗ:

    - FORCE_ON  => True
    - FORCE_OFF => False
    - AUTO      => True, только если текущее время в диапазоне 14:00–19:00.
    """
    mode = get_voice_mode()

    if mode is VoiceMode.FORCE_ON:
        return True
    if mode is VoiceMode.FORCE_OFF:
        return False

    # AUTO
    return _is_in_schedule(now)


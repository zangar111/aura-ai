"""Пользователи, которые заблокировали бота.

Им нельзя писать, поэтому бот не проверяет их оценки и не шлёт
уведомления, пока они снова не напишут боту. Данные пользователя
при этом не удаляются.

Список хранится в памяти: после перезапуска бот один раз попробует
написать такому пользователю, получит отказ и снова внесёт его сюда.
"""

import logging

logger = logging.getLogger(__name__)

_blocked: set[int] = set()


def is_blocked(telegram_id: int) -> bool:
    return telegram_id in _blocked


def blocked_ids() -> list[int]:
    return list(_blocked)


def mark_blocked(telegram_id: int):
    if telegram_id not in _blocked:
        _blocked.add(telegram_id)
        logger.info(
            "Пользователь %s заблокировал бота — проверки приостановлены, "
            "данные сохранены.",
            telegram_id,
        )


def mark_active(telegram_id: int):
    if telegram_id in _blocked:
        _blocked.discard(telegram_id)
        logger.info(
            "Пользователь %s снова пишет боту — проверки возобновлены.",
            telegram_id,
        )

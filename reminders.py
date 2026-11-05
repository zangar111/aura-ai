"""Отправка напоминаний по заметкам."""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from blocked_users import blocked_ids, mark_blocked
from database import DatabaseError, get_due_reminders, mark_reminded

logger = logging.getLogger(__name__)


async def send_due_reminders(bot: Bot, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            # Напоминания заблокировавшим бота ждут, пока они вернутся.
            reminders = await asyncio.to_thread(
                get_due_reminders,
                exclude_ids=blocked_ids(),
            )
        except DatabaseError as error:
            logger.warning(
                "Не удалось загрузить напоминания: %s", type(error).__name__
            )
            reminders = []

        for note in reminders:
            text = f"⏰ Напоминание: {note['topic']}\n\n{note['original_text']}"

            if note["url"] and note["url"] not in text:
                text += f"\n{note['url']}"

            try:
                await bot.send_message(
                    chat_id=note["telegram_id"],
                    text=text[:4000],
                    parse_mode=None,
                )
            except TelegramForbiddenError:
                # Не отмечаем как отправленное: напомним, когда вернётся.
                mark_blocked(note["telegram_id"])
                continue
            except TelegramAPIError as error:
                # Другие ошибки Telegram при повторе обычно не исчезают.
                logger.warning(
                    "Напоминание %s не отправлено: %s",
                    note["id"],
                    type(error).__name__,
                )

            try:
                await asyncio.to_thread(mark_reminded, note["id"])
            except DatabaseError as error:
                logger.warning(
                    "Не удалось отметить напоминание: %s", type(error).__name__
                )

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass

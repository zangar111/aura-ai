"""Постепенная «печать» ответа ИИ в Telegram.

Telegram умеет показывать черновик сообщения (sendMessageDraft):
текст плавно дописывается на глазах, а пустой черновик выглядит
как «Thinking…». Под черновиком — кнопка остановки.
Черновик временный: итоговое сообщение бот отправляет обычным
sendMessage, и черновик при этом исчезает сам.
"""

import asyncio
import logging
import random

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter

from formatting import markdown_to_html, strip_markdown

logger = logging.getLogger(__name__)

# Не чаще одного обновления черновика за столько секунд.
UPDATE_INTERVAL = 0.35
# Черновик ограничен 4096 символами; длинный ответ показываем с начала.
DRAFT_LIMIT = 3800

STATUSES = {
    "kk": {
        "get_grades": "📊 Бағаларды қарап жатырмын…",
        "get_grade_changes": "🆕 Өзгерістерді тексеріп жатырмын…",
        "show_grades": "📊 Журналды Platonus-тан жүктеп жатырмын…",
        "show_grade_chart": "📈 График салып жатырмын…",
        "get_schedule": "📅 Кестені қарап жатырмын…",
        "save_note": "📝 Жазбаны сақтап жатырмын…",
        "search_notes": "🔎 Жазбаларды іздеп жатырмын…",
        "delete_note": "🗑 Жазбаны өшіріп жатырмын…",
        "update_note": "✏️ Жазбаны өзгертіп жатырмын…",
        "default": "⏳ Орындап жатырмын…",
        "stopped": "⏹ Тоқтатылды",
    },
    "ru": {
        "get_grades": "📊 Смотрю оценки…",
        "get_grade_changes": "🆕 Проверяю изменения…",
        "show_grades": "📊 Загружаю журнал из Platonus…",
        "show_grade_chart": "📈 Рисую график…",
        "get_schedule": "📅 Смотрю расписание…",
        "save_note": "📝 Сохраняю заметку…",
        "search_notes": "🔎 Ищу заметки…",
        "delete_note": "🗑 Удаляю заметку…",
        "update_note": "✏️ Изменяю заметку…",
        "default": "⏳ Выполняю…",
        "stopped": "⏹ Остановлено",
    },
}

# Идущие ответы: (chat_id, draft_id) → черновик. Нужен кнопке «Стоп».
_active: dict[tuple[int, int], "DraftStreamer"] = {}


def stop_generation(chat_id: int, draft_id: int) -> bool:
    """Пользователь нажал «Остановить». False — ответ уже закончен."""
    streamer = _active.get((chat_id, draft_id))

    if streamer is None:
        return False

    streamer.stopped = True
    return True


class DraftStreamer:
    def __init__(self, bot: Bot, chat_id: int, language: str):
        self.bot = bot
        self.chat_id = chat_id
        self.statuses = STATUSES.get(language, STATUSES["kk"])
        self.draft_id = random.randint(1, 2**31 - 1)
        self.stopped = False
        # Если Telegram не принимает черновики — просто не показываем их.
        self.enabled = True
        # После таблицы оценок короткую фразу ИИ не показываем вовсе.
        self.muted = False

        self._latest: str | None = None
        self._sent: str | None = None
        self._wakeup = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        _active[(self.chat_id, self.draft_id)] = self
        self._task = asyncio.create_task(self._flush_loop())
        # Пустой черновик Telegram показывает как «Thinking…».
        await self._send("", html=False)
        return self

    async def __aexit__(self, *exc_info):
        _active.pop((self.chat_id, self.draft_id), None)

        if self._task is not None:
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def should_stop(self) -> bool:
        return self.stopped

    async def on_event(self, kind: str, value: str):
        """Событие от ask_ai: вызов функции или новый текст ответа."""
        if self.stopped or self.muted:
            return

        if kind == "tool":
            # Статус показываем сразу, без ожидания.
            status = self.statuses.get(value, self.statuses["default"])
            self._latest = None
            await self._send(f"<i>{status}</i>", html=True)
        elif kind == "text" and value.strip():
            self._latest = value
            self._wakeup.set()

    async def _flush_loop(self):
        # Отдельная задача: ИИ не ждёт Telegram, а Telegram получает
        # только последнее состояние текста, не чаще UPDATE_INTERVAL.
        while True:
            await self._wakeup.wait()
            self._wakeup.clear()

            text = self._latest

            if text is not None and text != self._sent and not self.muted and not self.stopped:
                await self._send(text, html=False)

            await asyncio.sleep(UPDATE_INTERVAL)

    async def _send(self, text: str, *, html: bool):
        if not self.enabled:
            return

        if not html and text:
            cut = text if len(text) <= DRAFT_LIMIT else text[:DRAFT_LIMIT] + " …"
            body, parse_mode = markdown_to_html(cut), "HTML"
        else:
            body, parse_mode = text, "HTML" if html else None

        try:
            await self.bot.send_message_draft(
                chat_id=self.chat_id,
                draft_id=self.draft_id,
                text=body,
                parse_mode=parse_mode,
                can_stop=True,
                keep_on_stop=True,
            )
            self._sent = text
        except TelegramRetryAfter as error:
            # Telegram просит притормозить — пропускаем обновление.
            await asyncio.sleep(min(error.retry_after, 5))
        except TelegramBadRequest as error:
            if parse_mode and "parse" in str(error).lower():
                # Незакрытая разметка в середине ответа — покажем без неё.
                await self._send_plain(text)
            else:
                logger.info("Черновики недоступны: %s", error)
                self.enabled = False
        except TelegramAPIError as error:
            logger.info("Черновик не обновлён: %s", type(error).__name__)

    async def _send_plain(self, text: str):
        try:
            await self.bot.send_message_draft(
                chat_id=self.chat_id,
                draft_id=self.draft_id,
                text=strip_markdown(text[:DRAFT_LIMIT]),
                parse_mode=None,
                can_stop=True,
                keep_on_stop=True,
            )
            self._sent = text
        except TelegramAPIError:
            pass

    @property
    def stopped_label(self) -> str:
        return self.statuses["stopped"]

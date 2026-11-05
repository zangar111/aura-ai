"""Обычные сообщения: разговор с ИИ."""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.types import Message, MessageGenerationStopped
from openai import APIError
from playwright.async_api import Error as BrowserError

from ai_client import ask_ai
from assistant_tools import ToolContext, ToolError, execute_tool, note_for_ai
from config import DEFAULT_TIMEZONE
from database import (
    DatabaseError,
    get_chat_history,
    get_notes,
    get_timezone,
    get_user,
    save_dialogue,
)
from formatting import markdown_to_html, split_message, strip_markdown
from grades_service import (
    chart_button,
    grades_in_progress,
    send_grade_chart,
    show_grades,
    store_grades,
    user_language,
)
from notes_search import select_relevant_notes
from parser import fetch_grades
from streaming import DraftStreamer, stop_generation

router = Router(name="assistant")
router.message.filter(F.chat.type == "private")


@router.stopped_message_generation()
async def generation_stopped(event: MessageGenerationStopped):
    # Кнопка «Остановить» под черновиком ответа.
    stop_generation(event.chat.id, event.draft_id)


async def user_timezone(telegram_id: int) -> ZoneInfo:
    try:
        name = await asyncio.to_thread(get_timezone, telegram_id)
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (DatabaseError, ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


async def fetch_grades_for_ai(message: Message) -> list[dict] | None:
    """Свежий журнал для ответа ИИ. None — Platonus не подключён."""
    telegram_id = message.from_user.id

    if telegram_id in grades_in_progress:
        raise ToolError("Журнал уже загружается. Попроси подождать минуту.")

    grades_in_progress.add(telegram_id)

    try:
        user = await asyncio.to_thread(get_user, telegram_id)

        if user is None:
            return None

        login, password = user

        try:
            grades = await fetch_grades(
                login,
                password,
                session_key=str(telegram_id),
            )
        except (BrowserError, ValueError):
            raise ToolError(
                "Не удалось войти в Platonus или загрузить журнал. "
                "Возможно, нужна капча или сайт недоступен."
            )

        if grades:
            try:
                # Оценки разберёт сам ИИ в ответе — отдельная сводка не нужна.
                await store_grades(
                    message.bot,
                    telegram_id,
                    grades,
                    with_summary=False,
                )
            except (ValueError, TelegramAPIError):
                # Журнал получен — для ответа этого достаточно.
                pass

        return grades
    finally:
        grades_in_progress.discard(telegram_id)


@router.message(
    StateFilter(None),
    F.text,
    ~F.text.startswith("/"),
)
async def ai_message(message: Message):
    if message.from_user is None:
        return

    telegram_id = message.from_user.id

    try:
        history = await asyncio.to_thread(get_chat_history, telegram_id)
        all_notes = await asyncio.to_thread(get_notes, telegram_id)
    except DatabaseError:
        await message.answer(
            "Не удалось загрузить историю и заметки. Попробуй позже."
        )
        return

    tz = await user_timezone(telegram_id)
    now = datetime.now(tz)

    ctx = ToolContext(
        telegram_id=telegram_id,
        user_text=message.text,
        notes=all_notes,
        tz=tz,
        now=now,
        show_grades=lambda: show_grades(message),
        fetch_grades=lambda: fetch_grades_for_ai(message),
        show_chart=lambda subject: send_grade_chart(
            message.bot,
            message.chat.id,
            telegram_id,
            subject,
        ),
    )

    notes_for_ai = [
        note_for_ai(note, tz)
        for note in select_relevant_notes(all_notes, message.text)
    ]

    language = await user_language(telegram_id)

    try:
        # Ответ «печатается» в черновике: сначала «Thinking…»,
        # потом статусы («Смотрю оценки…») и сам текст.
        async with DraftStreamer(message.bot, message.chat.id, language) as streamer:

            async def on_event(kind: str, value: str):
                # После таблицы оценок короткую фразу ИИ не показываем.
                if ctx.reply_optional:
                    streamer.muted = True

                await streamer.on_event(kind, value)

            text = await ask_ai(
                message.text,
                execute_tool=lambda name, arguments: execute_tool(
                    ctx, name, arguments
                ),
                now=now,
                history=history,
                notes=notes_for_ai,
                total_notes=len(all_notes),
                on_event=on_event,
                should_stop=streamer.should_stop,
            )
    except APIError:
        await message.answer(
            "Сейчас не удалось связаться с ИИ. Попробуй чуть позже."
        )
        return

    # Итоговое сообщение — после выхода из черновика: оно его заменяет.
    text = text.strip()

    if streamer.stopped:
        # Сохраняем то, что успело напечататься, с пометкой.
        text = f"{text}\n\n_{streamer.stopped_label}_" if text else streamer.stopped_label
    elif ctx.reply_optional and len(text) <= 80:
        # Таблица и сводка уже отправлены — фраза «кесте жіберілді»
        # ничего не добавит.
        text = ""
    elif not text:
        text = "Попробуй сформулировать запрос иначе."

    chunks = split_message(text) if text else []

    # Ответ об оценках — под ним предложим график прогресса,
    # если ИИ не отправил его сам.
    keyboard = None

    if ctx.offer_chart and not ctx.reply_optional and not streamer.stopped:
        keyboard = chart_button(language)

    for index, chunk in enumerate(chunks):
        markup = keyboard if index == len(chunks) - 1 else None

        try:
            await message.answer(
                markdown_to_html(chunk),
                parse_mode="HTML",
                reply_markup=markup,
            )
        except TelegramBadRequest:
            # Telegram не принял разметку — отправим без неё.
            await message.answer(
                strip_markdown(chunk),
                parse_mode=None,
                reply_markup=markup,
            )
        await asyncio.sleep(0.5)

    # В историю попадают и выполненные действия, чтобы ИИ их помнил.
    saved_reply = " ".join([*ctx.actions, text]) if ctx.actions else text

    try:
        await asyncio.to_thread(
            save_dialogue,
            telegram_id,
            message.text,
            saved_reply,
        )
    except DatabaseError:
        await message.answer(
            "Ответ отправлен, но сохранить его в историю не удалось."
        )

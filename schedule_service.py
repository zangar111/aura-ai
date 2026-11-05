"""Расписание: загрузка из Platonus, утренний дайджест, напоминания о парах."""

import asyncio
import logging
from datetime import datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from blocked_users import is_blocked, mark_blocked
from config import DEFAULT_LANGUAGE, DEFAULT_TIMEZONE
from database import (
    DatabaseError,
    get_grade_changes_since,
    get_language,
    get_notes_due_between,
    get_schedule,
    get_schedule_recipients,
    get_timezone,
    get_user,
    mark_digest_sent,
    save_schedule,
)
from grade_changes import is_important
from parser import fetch_schedule
from schedule import format_date, format_lesson, lesson_start, lessons_on, normalize, week_number

logger = logging.getLogger(__name__)

# Расписание старше этого обновляется при очередной проверке.
SCHEDULE_MAX_AGE = timedelta(hours=12)
# После неудачной загрузки — не чаще, чем раз в столько.
RETRY_AFTER = timedelta(hours=2)
# За сколько минут до пары напоминать.
LESSON_REMINDER_MINUTES = 15
# Дайджест, опоздавший больше чем на столько (бот был выключен), не шлём.
DIGEST_LATE_LIMIT = timedelta(hours=3)

TEXTS = {
    "kk": {
        "morning": "☀️ <b>Қайырлы таң!</b>",
        "today": "Бүгін",
        "week": "{n}-апта",
        "lessons": "📚 <b>Бүгінгі сабақтар</b> ({count})",
        "no_lessons": "📚 Бүгін сабақ жоқ — демалыңыз 🎉",
        "first": "Бірінші сабақ — {time}",
        "reminders": "⏰ <b>Бүгінгі еске салулар</b>",
        "grades": "🆕 <b>Тәулік ішінде жаңа бағалар</b> ({count})",
        "soon": "⏰ <b>{minutes} минуттан кейін сабақ:</b>",
        "week_button": "📅 Апта кестесі",
        "not_connected": "Алдымен Platonus-ты қосыңыз: /connect",
        "loading": "Кестені Platonus-тан жүктеп жатырмын…",
        "failed": "Кестені жүктеу мүмкін болмады. Кейінірек қайталаңыз.",
    },
    "ru": {
        "morning": "☀️ <b>Доброе утро!</b>",
        "today": "Сегодня",
        "week": "{n}-я неделя",
        "lessons": "📚 <b>Пары сегодня</b> ({count})",
        "no_lessons": "📚 Сегодня пар нет — отдыхай 🎉",
        "first": "Первая пара — в {time}",
        "reminders": "⏰ <b>Напоминания на сегодня</b>",
        "grades": "🆕 <b>Новые оценки за сутки</b> ({count})",
        "soon": "⏰ <b>Через {minutes} минут пара:</b>",
        "week_button": "📅 Расписание на неделю",
        "not_connected": "Сначала подключи Platonus: /connect",
        "loading": "Загружаю расписание из Platonus…",
        "failed": "Не удалось загрузить расписание. Попробуй позже.",
    },
}

# Пользователи, для которых сейчас идёт загрузка, и время неудачных попыток.
refresh_in_progress: set[int] = set()
_failed_at: dict[int, datetime] = {}
# Уже отправленные напоминания о парах: (telegram_id, дата, начало).
_sent_lesson_reminders: set[tuple] = set()


def texts_for(language: str | None) -> dict:
    return TEXTS.get(language or DEFAULT_LANGUAGE, TEXTS[DEFAULT_LANGUAGE])


def _timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


async def user_settings(telegram_id: int) -> tuple[str, ZoneInfo]:
    try:
        language = await asyncio.to_thread(get_language, telegram_id)
        tz_name = await asyncio.to_thread(get_timezone, telegram_id)
    except DatabaseError:
        language, tz_name = None, None

    language = language if language in TEXTS else DEFAULT_LANGUAGE
    return language, _timezone(tz_name)


async def refresh_schedule(telegram_id: int, *, background: bool = True) -> dict | None:
    """Загружает расписание из Platonus и сохраняет. None — Platonus не подключён."""
    user = await asyncio.to_thread(get_user, telegram_id)

    if user is None:
        return None

    login, password = user
    language, _ = await user_settings(telegram_id)

    try:
        raw = await fetch_schedule(
            login,
            password,
            background=background,
            session_key=str(telegram_id),
            language=language,
        )
        schedule = normalize(raw)
    except Exception:
        _failed_at[telegram_id] = datetime.now(ZoneInfo("UTC"))
        raise

    await asyncio.to_thread(save_schedule, telegram_id, schedule)
    _failed_at.pop(telegram_id, None)
    return schedule


async def refresh_if_stale(telegram_id: int):
    """Для фоновой проверки: обновить расписание, если оно устарело.

    Никогда не бросает исключений: сбой расписания не должен
    мешать проверке оценок.
    """
    now = datetime.now(ZoneInfo("UTC"))
    failed = _failed_at.get(telegram_id)

    if failed is not None and now - failed < RETRY_AFTER:
        return

    try:
        stored = await asyncio.to_thread(get_schedule, telegram_id)

        if stored is not None and now - stored[1] < SCHEDULE_MAX_AGE:
            return

        await refresh_schedule(telegram_id)
        logger.info("Расписание пользователя %s обновлено.", telegram_id)
    except Exception as error:
        _failed_at[telegram_id] = now
        logger.warning(
            "Расписание пользователя %s не обновлено: %s",
            telegram_id,
            type(error).__name__,
        )


async def load_schedule(telegram_id: int, *, refresh: bool = False) -> dict | None:
    """Сохранённое расписание; если его нет или просят — загрузить."""
    if not refresh:
        stored = await asyncio.to_thread(get_schedule, telegram_id)

        if stored is not None:
            return stored[0]

    if telegram_id in refresh_in_progress:
        raise RuntimeError("Расписание уже загружается.")

    refresh_in_progress.add(telegram_id)

    try:
        return await refresh_schedule(telegram_id, background=False)
    finally:
        refresh_in_progress.discard(telegram_id)


def week_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts_for(language)["week_button"],
                    callback_data="schedule:week",
                )
            ]
        ]
    )


async def build_digest(telegram_id: int, schedule: dict, language: str, tz: ZoneInfo) -> str:
    texts = texts_for(language)
    now = datetime.now(tz)
    today = now.date()
    lessons = lessons_on(schedule, today)

    header = f"{texts['morning']}\n{texts['today']} — {format_date(today, language)}"
    week = week_number(schedule, today)

    if week and lessons:
        header += f" · {texts['week'].format(n=week)}"

    blocks = [header]

    if lessons:
        blocks.append(
            texts["lessons"].format(count=len(lessons))
            + "\n"
            + texts["first"].format(time=lessons[0]["start"])
            + "\n\n"
            + "\n\n".join(format_lesson(lesson, language) for lesson in lessons)
        )
    else:
        blocks.append(texts["no_lessons"])

    start_of_day = datetime.combine(today, time.min, tzinfo=tz)
    reminders = await asyncio.to_thread(
        get_notes_due_between,
        telegram_id,
        start_of_day,
        start_of_day + timedelta(days=1),
    )

    if reminders:
        blocks.append(
            texts["reminders"]
            + "\n"
            + "\n".join(
                f"• {note['remind_at'].astimezone(tz):%H:%M} — {escape(note['topic'])}"
                for note in reminders
            )
        )

    changes = await asyncio.to_thread(get_grade_changes_since, telegram_id, 1)
    # Только оценки за неделю, рубежки и итоги — без пересчётов ТК и рейтинга.
    new_marks = [
        change
        for change in changes
        if change["new_value"] and is_important(change["column"])
    ]

    if new_marks:
        lines = []

        for change in new_marks[:5]:
            column = change["column"]
            label = f"{column}-апта" if language == "kk" and column.isdigit() else (
                f"неделя {column}" if column.isdigit() else column
            )
            lines.append(
                f"• {escape(change['subject'])} · {escape(label)}: <b>{escape(change['new_value'])}</b>"
            )

        blocks.append(texts["grades"].format(count=len(new_marks)) + "\n" + "\n".join(lines))

    return "\n\n".join(blocks)


async def _send(bot: Bot, telegram_id: int, text: str, keyboard=None) -> bool:
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text[:4000],
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return True
    except TelegramForbiddenError:
        mark_blocked(telegram_id)
    except TelegramAPIError as error:
        logger.warning("Сообщение %s не отправлено: %s", telegram_id, type(error).__name__)

    return False


async def _process_recipient(bot: Bot, recipient: dict):
    telegram_id = recipient["telegram_id"]

    if is_blocked(telegram_id):
        return

    language = recipient["language_code"] if recipient["language_code"] in TEXTS else DEFAULT_LANGUAGE
    tz = _timezone(recipient["timezone_name"])
    schedule = recipient["schedule"]
    now = datetime.now(tz)
    today = now.date()

    # Утренний дайджест — один раз в день, в выбранное время.
    if recipient["digest_enabled"] and recipient["last_digest_on"] != today:
        digest_at = datetime.combine(today, recipient["digest_time"], tzinfo=tz)

        if digest_at <= now < digest_at + DIGEST_LATE_LIMIT:
            text = await build_digest(telegram_id, schedule, language, tz)

            if await _send(bot, telegram_id, text, week_keyboard(language)):
                await asyncio.to_thread(mark_digest_sent, telegram_id, today)

    # Напоминание о паре за 15 минут.
    if recipient["lesson_reminders"]:
        for lesson in lessons_on(schedule, today):
            starts = lesson_start(lesson, today, tz)
            key = (telegram_id, today, lesson["start"])

            if key in _sent_lesson_reminders:
                continue

            if starts - timedelta(minutes=LESSON_REMINDER_MINUTES) <= now < starts:
                minutes = max(1, round((starts - now).total_seconds() / 60))
                text = (
                    texts_for(language)["soon"].format(minutes=minutes)
                    + "\n\n"
                    + format_lesson(lesson, language)
                )
                _sent_lesson_reminders.add(key)
                await _send(bot, telegram_id, text)


async def run_schedule_notifications(bot: Bot, stop_event: asyncio.Event):
    """Раз в минуту: утренние дайджесты и напоминания о парах."""
    while not stop_event.is_set():
        try:
            recipients = await asyncio.to_thread(get_schedule_recipients)
        except DatabaseError as error:
            logger.warning("Не удалось загрузить расписания: %s", type(error).__name__)
            recipients = []

        for recipient in recipients:
            try:
                await _process_recipient(bot, recipient)
            except Exception:
                logger.exception("Дайджест/напоминание для %s не удалось", recipient["telegram_id"])

        # Старые отметки о напоминаниях больше не нужны.
        yesterday = datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).date() - timedelta(days=1)
        _sent_lesson_reminders.difference_update(
            {key for key in _sent_lesson_reminders if key[1] < yesterday}
        )

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass

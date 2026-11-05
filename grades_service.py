"""Загрузка, сохранение и показ журнала оценок."""

import asyncio
import logging
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputRichMessage,
    Message,
    WebAppInfo,
)
from aiogram.utils.chat_action import ChatActionSender
from openai import APIError
from playwright.async_api import Error as BrowserError

from ai_client import summarize_grades
from blocked_users import is_blocked, mark_blocked
from config import DEFAULT_LANGUAGE, DEFAULT_TIMEZONE
from database import (
    DatabaseError,
    get_connected_user_ids,
    get_grade_snapshot,
    get_language,
    get_pending_grade_changes,
    get_recent_grade_changes,
    get_user,
    mark_grade_changes_notified,
    save_grade_snapshot,
)
from grade_changes import JournalStructureChanged, is_important, journal_structure
from grade_chart import find_subject, render_progress_chart, weekly_series
from grade_summary import compact_grades
from parser import fetch_grades, is_browser_gone
from schedule import TYPE_NAMES
from schedule_service import refresh_if_stale
from webapp_server import public_url, public_url_is_stable

logger = logging.getLogger(__name__)

grades_in_progress = set()


# Новая структура журнала, ожидающая подтверждения второй загрузкой.
pending_structures: dict[int, frozenset] = {}


def format_grades(grades, recent_changes=None) -> str:
    changes_by_cell = {
        (
            " ".join(item["subject"].split()).rstrip("_").strip(),
            " ".join(item["stream"].split()),
            " ".join(item["column"].split()),
        ): item
        for item in (recent_changes or [])
    }

    markers = {
        "new": "🆕",
        "updated": "🔄",
        "removed": "➖",
    }

    subjects = {}

    for row in grades:
        subject = " ".join(row["subject"].split()).rstrip("_").strip()
        subjects.setdefault(subject, []).append(row)

    blocks = [
        "<p><b>📊 Твои оценки</b></p>",
        "<p>Нажми на предмет, чтобы раскрыть журнал.<br>"
        "Отдельно показаны оценки по неделям и результаты. "
        "Пустые ячейки обозначены «—».</p>",
        "<p>🆕 — новая · 🔄 — изменённая · ➖ — удалённая.<br>"
        "Пометки показывают изменения за последние 24 часа.</p>",
    ]

    for subject, rows in subjects.items():
        columns = list(
            dict.fromkeys(
                column
                for row in rows
                for column in row["marks"]
            )
        )

        weeks = sorted(
            [column for column in columns if column.isdigit()],
            key=int,
        )

        results = [
            column
            for column in columns
            if not column.isdigit()
        ]

        labels = []

        for row in rows:
            stream = row["stream"].strip()
            kind = stream.rsplit("-", 1)[-1].strip()
            labels.append(kind or "Не указан")

        groups = [
            ("Оценки по неделям", weeks),
            ("ТК, РК и итоги", results),
        ]

        tables = []

        for title, group_columns in groups:
            # До 19 показателей плюс первый столбец «Тип».
            for start in range(0, len(group_columns), 19):
                table_columns = group_columns[start:start + 19]

                caption = title

                if len(group_columns) > 19:
                    caption += f" · часть {start // 19 + 1}"

                header = (
                    "<tr><th>Тип</th>"
                    + "".join(
                        f"<th>{escape(column)}</th>"
                        for column in table_columns
                    )
                    + "</tr>"
                )

                table_rows = [header]

                for index, row in enumerate(rows):
                    label = labels[index]

                    if labels.count(label) > 1:
                        label = row["stream"].strip() or label

                    cells = [f"<td>{escape(label)}</td>"]

                    for column in table_columns:
                        value = row["marks"].get(column)
                        text = (
                            ""
                            if value is None
                            else str(value).strip()
                        )

                        key = (
                            subject,
                            " ".join(row["stream"].split()),
                            " ".join(column.split()),
                        )

                        cell_text = escape(text) if text else "—"
                        change = changes_by_cell.get(key)

                        if (
                                change is not None
                                and column in row["marks"]
                                and change["new_value"] == text
                        ):
                            marker = markers.get(change["kind"])

                            if marker:
                                cell_text = (
                                    f"<mark><b>{cell_text}</b></mark> "
                                    f"{marker}"
                                )

                        cells.append(f"<td>{cell_text}</td>")
                    table_rows.append(
                        "<tr>" + "".join(cells) + "</tr>"
                    )

                tables.append(
                    "<table bordered striped compact>"
                    f"<caption>{escape(caption)}</caption>"
                    + "".join(table_rows)
                    + "</table>"
                )

        content = (
            "".join(tables)
            if tables
            else "<p>В журнале пока нет записей.</p>"
        )

        blocks.append(
            "<details>"
            f"<summary>📘 {escape(subject)}</summary>"
            + content
            + "</details>"
        )

    return "".join(blocks)


SUMMARY_LABELS = {
    "kk": {
        "title": "Бағалар бойынша қысқаша шолу",
        "changes": "Жаңа бағалар",
        "overall": "Жалпы жағдай",
        "risks": "Назар аудару керек",
        "tip": "Кеңес",
    },
    "ru": {
        "title": "Краткая сводка по оценкам",
        "changes": "Новые оценки",
        "overall": "В целом",
        "risks": "Обратить внимание",
        "tip": "Совет",
    },
}


def render_grade_summary(summary: dict, language: str) -> str:
    """Собирает сводку в единый вид (HTML для Telegram)."""
    labels = SUMMARY_LABELS.get(language, SUMMARY_LABELS[DEFAULT_LANGUAGE])
    blocks = [f"📊 <b>{labels['title']}</b>"]

    def bullets(items: list[str]) -> str:
        return "\n".join(f"• {escape(item)}" for item in items)

    if summary.get("changes"):
        blocks.append(
            f"🆕 <b>{labels['changes']}</b>\n{bullets(summary['changes'])}"
        )

    if summary.get("overall"):
        blocks.append(
            f"✅ <b>{labels['overall']}</b>\n{escape(summary['overall'])}"
        )

    if summary.get("risks"):
        blocks.append(
            f"⚠️ <b>{labels['risks']}</b>\n{bullets(summary['risks'])}"
        )

    if summary.get("tip"):
        blocks.append(f"💡 <b>{labels['tip']}:</b> {escape(summary['tip'])}")

    return "\n\n".join(blocks)


CHART_TEXTS = {
    "kk": {
        "button": "📈 Прогресс графигі",
        "caption": (
            "📈 Прогресс графигі\n"
            "Бір пән бойынша: «блокчейн графигін көрсет» деп жазыңыз."
        ),
        "no_grades": "Әзірге журнал сақталмаған. Алдымен /grades жіберіңіз.",
        "app": "📱 Журнал",
    },
    "ru": {
        "button": "📈 График прогресса",
        "caption": (
            "📈 График прогресса\n"
            "По одному предмету: напиши «покажи график по блокчейну»."
        ),
        "no_grades": "Журнал ещё не сохранён. Сначала отправь /grades.",
        "app": "📱 Журнал",
    },
}


async def user_language(telegram_id: int) -> str:
    try:
        language = await asyncio.to_thread(get_language, telegram_id)
    except DatabaseError:
        language = None

    return language if language in CHART_TEXTS else DEFAULT_LANGUAGE


def chart_button(language: str) -> InlineKeyboardMarkup:
    """Кнопки под сообщениями об оценках: график и, если есть, Mini App."""
    texts = CHART_TEXTS.get(language, CHART_TEXTS[DEFAULT_LANGUAGE])
    row = [InlineKeyboardButton(text=texts["button"], callback_data="chart")]
    url = public_url()

    # Адрес временного туннеля устареет после перезапуска бота,
    # а кнопка в сообщении останется. Тогда Mini App открывают
    # кнопкой меню «Aura» или командой /app — там адрес всегда свежий.
    if url and public_url_is_stable():
        row.append(
            InlineKeyboardButton(text=texts["app"], web_app=WebAppInfo(url=url))
        )

    return InlineKeyboardMarkup(inline_keyboard=[row])


class UnknownSubject(ValueError):
    def __init__(self, subjects: list[str]):
        super().__init__("Такого предмета нет в журнале.")
        self.subjects = subjects


async def send_grade_chart(
    bot: Bot,
    chat_id: int,
    telegram_id: int,
    subject_query: str | None = None,
) -> str | None:
    """Отправляет график прогресса из сохранённого журнала.

    Возвращает название предмета (или None — все предметы).
    Platonus не открывается: берётся журнал из последней проверки.
    """
    language = await user_language(telegram_id)
    texts = CHART_TEXTS[language]
    snapshot = await asyncio.to_thread(get_grade_snapshot, telegram_id)

    if snapshot is None:
        await bot.send_message(chat_id=chat_id, text=texts["no_grades"])
        return None

    grades, fetched_at = snapshot
    subject = None

    if subject_query:
        subjects = list(weekly_series(grades))
        subject = find_subject(subjects, subject_query)

        if subject is None:
            raise UnknownSubject(subjects)

    local_time = fetched_at.astimezone(ZoneInfo(DEFAULT_TIMEZONE))

    async with ChatActionSender.upload_photo(bot=bot, chat_id=chat_id):
        image = await asyncio.to_thread(
            render_progress_chart,
            grades,
            language,
            subject,
            f"{local_time:%d.%m.%Y %H:%M} · Platonus",
        )
        await bot.send_photo(
            chat_id=chat_id,
            photo=BufferedInputFile(image, filename="progress.png"),
            caption=texts["caption"],
        )

    return subject


async def send_grade_summary(
    bot: Bot,
    telegram_id: int,
    grades: list[dict],
    changes: list[dict] | None = None,
):
    """Отправляет краткую сводку оценок от ИИ.

    Сводка — дополнение: если ИИ или Telegram недоступны,
    ошибка только пишется в лог.
    """
    try:
        language = (
            await asyncio.to_thread(get_language, telegram_id)
            or DEFAULT_LANGUAGE
        )
        summary = await summarize_grades(
            compact_grades(grades),
            changes,
            language,
        )

        if not any(summary.values()):
            return

        # Под сводкой — предложение посмотреть график.
        await bot.send_message(
            chat_id=telegram_id,
            text=render_grade_summary(summary, language),
            parse_mode="HTML",
            reply_markup=chart_button(language),
        )
    except TelegramForbiddenError:
        mark_blocked(telegram_id)
    except (APIError, DatabaseError, TelegramAPIError, ValueError) as error:
        logger.warning(
            "Сводка оценок для %s не отправлена: %s",
            telegram_id,
            type(error).__name__,
        )


CHANGE_TEXTS = {
    "kk": {
        "title_new": "🔔 <b>Жаңа бағалар</b>",
        "title_changed": "🔔 <b>Бағалардағы өзгерістер</b>",
        "week": "{n}-апта",
        "removed": "өшірілді",
        "footer": "Толық журнал: /grades",
        "columns": {
            "Итоговый контроль": "Емтихан",
            "Итоговая оценка (Буквенная)": "Қорытынды баға",
            "Оценка за курсовую работу": "Курстық жұмыс",
            "Исследоват. работа": "Зерттеу жұмысы",
        },
    },
    "ru": {
        "title_new": "🔔 <b>Новые оценки</b>",
        "title_changed": "🔔 <b>Изменения в оценках</b>",
        "week": "{n}-я неделя",
        "removed": "удалена",
        "footer": "Полный журнал: /grades",
        "columns": {
            "Итоговый контроль": "Экзамен",
            "Итоговая оценка (Буквенная)": "Итоговая оценка",
            "Оценка за курсовую работу": "Курсовая",
            "Исследоват. работа": "Исследовательская работа",
        },
    },
}

TYPE_ORDER = {"L": 0, "Lab": 1, "Pr": 2, "SRO": 3}

# Запас до лимита Telegram в 4096 символов.
NOTIFICATION_LIMIT = 3500


def _change_line(change: dict, texts: dict, language: str) -> str:
    lesson_type = change["stream"].strip().rsplit("-", 1)[-1].strip()
    type_name = TYPE_NAMES.get(language, TYPE_NAMES["kk"]).get(lesson_type, lesson_type)
    column = " ".join(change["column"].split())
    column = (
        texts["week"].format(n=column)
        if column.isdigit()
        else texts["columns"].get(column, column)
    )
    old_value = escape(change["old_value"].strip())
    new_value = escape(change["new_value"].strip())

    if change["kind"] == "removed":
        value = f"<s>{old_value}</s> {texts['removed']}"
    elif change["kind"] == "updated" and old_value:
        value = f"<s>{old_value}</s> → <b>{new_value}</b>"
    else:
        value = f"<b>{new_value}</b>"

    return f"{escape(type_name)} · {escape(column)} — {value}"


def format_grade_changes(changes: list[dict], language: str) -> tuple[str, list[dict]]:
    """Изменения, сгруппированные по предметам. Возвращает (HTML, вошедшие).

    Не поместившиеся в одно сообщение предметы остаются на потом.
    """
    texts = CHANGE_TEXTS.get(language, CHANGE_TEXTS["kk"])
    by_subject: dict[str, list[dict]] = {}

    for change in changes:
        subject = " ".join(change["subject"].split()).rstrip("_").strip()
        by_subject.setdefault(subject, []).append(change)

    only_new = all(change["kind"] == "new" for change in changes)
    title = texts["title_new"] if only_new else texts["title_changed"]
    blocks, included = [], []

    def order(change: dict):
        lesson_type = change["stream"].strip().rsplit("-", 1)[-1].strip()
        column = change["column"].strip()
        return (
            TYPE_ORDER.get(lesson_type, 9),
            0 if column.isdigit() else 1,
            int(column) if column.isdigit() else 0,
            column,
        )

    for subject, items in by_subject.items():
        items = sorted(items, key=order)
        block = f"📘 <b>{escape(subject)}</b>\n" + "\n".join(
            _change_line(change, texts, language) for change in items
        )
        candidate = "\n\n".join([title, *blocks, block, texts["footer"]])

        if blocks and len(candidate) > NOTIFICATION_LIMIT:
            break

        blocks.append(block)
        included.extend(items)

    return "\n\n".join([title, *blocks, texts["footer"]]), included


async def notify_grade_changes(bot: Bot, telegram_id: int) -> list[dict]:
    """Отправляет новые важные изменения оценок. Возвращает отправленные.

    Пересчитанные столбцы (ТК, Р1, рейтинг допуска…) отмечаются
    как обработанные без уведомления.
    """
    pending = await asyncio.to_thread(
        get_pending_grade_changes,
        telegram_id,
    )

    if not pending:
        return []

    important = [change for change in pending if is_important(change["column"])]
    skipped = [change["id"] for change in pending if not is_important(change["column"])]

    if skipped:
        await asyncio.to_thread(mark_grade_changes_notified, telegram_id, skipped)

    if not important:
        return []

    language = await user_language(telegram_id)
    text, sent = format_grade_changes(important, language)

    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        parse_mode="HTML",
        disable_notification=False,
    )

    await asyncio.to_thread(
        mark_grade_changes_notified,
        telegram_id,
        [change["id"] for change in sent],
    )

    return sent


async def store_grades(
    bot: Bot,
    telegram_id: int,
    grades: list[dict],
    *,
    with_summary: bool = True,
):
    """Сохраняет журнал и уведомляет об изменениях.

    with_summary — после уведомления прислать краткую сводку оценок.
    Отключается, когда сводка будет отправлена другим путём
    (например, вместе с таблицей /grades).

    Если структура журнала изменилась (новый семестр, новые предметы),
    новый журнал принимается только после двух одинаковых загрузок
    подряд — так случайная неполная загрузка не сбросит историю.
    """
    try:
        await asyncio.to_thread(save_grade_snapshot, telegram_id, grades)
    except JournalStructureChanged:
        structure = journal_structure(grades)

        if pending_structures.get(telegram_id) != structure:
            pending_structures[telegram_id] = structure
            raise

        await asyncio.to_thread(
            save_grade_snapshot,
            telegram_id,
            grades,
            reset=True,
        )
        pending_structures.pop(telegram_id, None)

        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "📋 Журнал в Platonus изменился: появились или исчезли "
                "предметы и столбцы. Теперь слежу за новым журналом.\n\n"
                "Посмотреть его: /grades"
            ),
        )
        return

    pending_structures.pop(telegram_id, None)
    sent = await notify_grade_changes(bot, telegram_id)

    if sent and with_summary:
        await send_grade_summary(bot, telegram_id, grades, sent)


async def send_grades(message: Message):
    if message.from_user is None:
        return

    user = await asyncio.to_thread(get_user, message.from_user.id)

    if user is None:
        await message.answer("Сначала подключи Platonus через /connect.")
        return

    login, password = user
    progress = await message.answer("Получаю оценки, подожди…")

    try:
        grades = await fetch_grades(
            login,
            password,
            session_key=str(message.from_user.id),
        )
    except (BrowserError, ValueError):
        await message.answer(
            "Не удалось войти в Platonus или загрузить журнал. "
            "Проверь данные входа. Возможно, нужна капча "
            "или сайт временно недоступен."
        )
        return

    if not grades:
        await message.answer("В журнале нет строк с оценками.")
        return

    try:
        # Сводка придёт после таблицы, вторая не нужна.
        await store_grades(
            message.bot,
            message.from_user.id,
            grades,
            with_summary=False,
        )
    except DatabaseError:
        await message.answer(
            "Оценки загружены, но сохранить изменения "
            "не удалось из-за ошибки базы данных."
        )
    except JournalStructureChanged:
        await message.answer(
            "Похоже, в журнале изменились предметы или столбцы. "
            "Если при следующей проверке будет так же, "
            "я приму новый журнал как отправную точку."
        )
    except ValueError:
        await message.answer(
            "Оценки загружены, но сравнить журнал не удалось. "
            "Предыдущий журнал сохранён без изменений."
        )
    except TelegramAPIError:
        logger.warning("Не удалось отправить уведомление об изменениях.")

    try:
        recent_changes = await asyncio.to_thread(
            get_recent_grade_changes,
            message.from_user.id,
        )
    except DatabaseError:
        recent_changes = []

    html = format_grades(grades, recent_changes)

    await progress.edit_text(
        rich_message=InputRichMessage(html=html)
    )

    async with ChatActionSender.typing(
        bot=message.bot,
        chat_id=message.chat.id,
    ):
        await send_grade_summary(
            message.bot,
            message.from_user.id,
            grades,
            recent_changes,
        )


async def show_grades(message: Message):
    """Как /grades: не даёт загружать журнал дважды одновременно."""
    if message.from_user is None:
        return

    telegram_id = message.from_user.id

    if telegram_id in grades_in_progress:
        await message.answer("Уже получаю твои оценки. Подожди завершения.")
        return

    grades_in_progress.add(telegram_id)

    try:
        await send_grades(message)
    finally:
        grades_in_progress.discard(telegram_id)


# После неудачи проверка пользователя откладывается всё дольше,
# чтобы частые неудачные входы не заблокировали аккаунт.
MAX_BACKOFF_SECONDS = 12 * 60 * 60


# После стольких неудач подряд пользователь получает предупреждение.
FAILURES_BEFORE_WARNING = 3


async def monitor_grades(
    bot: Bot,
    interval_seconds: int,
    stop_event: asyncio.Event,
):
    loop = asyncio.get_running_loop()
    # telegram_id -> (неудач подряд, не проверять раньше этого времени)
    failures: dict[int, tuple[int, float]] = {}

    while not stop_event.is_set():
        started_at = loop.time()

        try:
            user_ids = await asyncio.to_thread(get_connected_user_ids)
        except Exception as error:
            logger.warning(
                "Не удалось загрузить список пользователей: %s",
                type(error).__name__,
            )
            user_ids = []

        for telegram_id in user_ids:
            if stop_event.is_set():
                break

            if telegram_id in grades_in_progress or is_blocked(telegram_id):
                continue

            failed_count, retry_at = failures.get(telegram_id, (0, 0.0))

            if loop.time() < retry_at:
                continue

            grades_in_progress.add(telegram_id)

            try:
                user = await asyncio.to_thread(get_user, telegram_id)
                if user is None:
                    continue

                login, password = user

                grades = await asyncio.wait_for(
                    fetch_grades(
                        login,
                        password,
                        background=True,
                        session_key=str(telegram_id),
                    ),
                    timeout=180,
                )

                failures.pop(telegram_id, None)

                # Сессия только что проверена — заодно обновим расписание,
                # если оно устарело (раз в 12 часов).
                await refresh_if_stale(telegram_id)

                if not grades:
                    continue

                await store_grades(bot, telegram_id, grades)

            except TelegramForbiddenError:
                # Журнал уже сохранён, не отправилось только сообщение.
                mark_blocked(telegram_id)
            except JournalStructureChanged:
                logger.info(
                    "Журнал пользователя %s изменил структуру, "
                    "жду подтверждения следующей загрузкой.",
                    telegram_id,
                )
            except (BrowserError, ValueError, asyncio.TimeoutError) as error:
                if is_browser_gone(error):
                    # Браузер закрыт (например, бота останавливают) —
                    # пароль ни при чём, остальных проверять бессмысленно.
                    logger.info("Браузер закрыт — проверка оценок прервана.")
                    break

                failed_count += 1
                delay = min(
                    interval_seconds * 2 ** failed_count,
                    MAX_BACKOFF_SECONDS,
                )
                failures[telegram_id] = (failed_count, loop.time() + delay)

                logger.warning(
                    "Не удалось загрузить журнал %s (%s раз подряд): %s",
                    telegram_id,
                    failed_count,
                    type(error).__name__,
                )

                if failed_count == FAILURES_BEFORE_WARNING:
                    try:
                        await bot.send_message(
                            chat_id=telegram_id,
                            text=(
                                "⚠️ Уже несколько раз не получается войти "
                                "в Platonus. Если ты менял пароль, "
                                "подключи аккаунт заново: /connect\n\n"
                                "Пока буду проверять оценки реже."
                            ),
                        )
                    except TelegramForbiddenError:
                        mark_blocked(telegram_id)
                    except TelegramAPIError:
                        pass
            except Exception:
                logger.exception(
                    "Проверка оценок пользователя %s не удалась",
                    telegram_id,
                )
            finally:
                grades_in_progress.discard(telegram_id)

        delay = max(1, interval_seconds - (loop.time() - started_at))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

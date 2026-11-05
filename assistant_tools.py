import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from psycopg import Error as DatabaseError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import database
from grade_summary import compact_grades
from grades_service import UnknownSubject
from schedule import lessons_for_ai, week_number
from schedule_service import load_schedule
from notes_search import search_notes


class Args(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )


class NoArgs(Args):
    pass


class GetGradesArgs(Args):
    refresh: bool = False


class ScheduleArgs(Args):
    day: str = Field(min_length=4, max_length=10)


class ChartArgs(Args):
    subject: str | None = Field(default=None, min_length=1, max_length=200)


class GradeChangesArgs(Args):
    days: int = Field(default=7, ge=1, le=120)


class SaveNoteArgs(Args):
    topic: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, min_length=1)
    remind_at: str | None = None


class SearchNotesArgs(Args):
    query: str = Field(min_length=1, max_length=200)


class DeleteNoteArgs(Args):
    note_id: int = Field(gt=0)


class UpdateNoteArgs(Args):
    note_id: int = Field(gt=0)
    topic: str = Field(min_length=1, max_length=200)
    original_text: str = Field(min_length=1)
    url: str | None = Field(min_length=1)
    remind_at: str | None


class ToolError(Exception):
    """Ошибка, о которой нужно сообщить ИИ, а он — пользователю."""


def parse_remind_at(value: str | None, tz: ZoneInfo, now: datetime) -> datetime | None:
    if value is None:
        return None

    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise ToolError("remind_at должен быть в формате YYYY-MM-DDTHH:MM.")

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)

    if moment < now - timedelta(minutes=1):
        raise ToolError("Время напоминания уже прошло. Уточни дату.")

    return moment


def local_time(moment: datetime | None, tz: ZoneInfo) -> str | None:
    return moment.astimezone(tz).strftime("%Y-%m-%dT%H:%M") if moment else None


def note_for_ai(note: dict, tz: ZoneInfo) -> dict:
    return {**note, "remind_at": local_time(note.get("remind_at"), tz)}


@dataclass
class ToolContext:
    """Всё, что нужно функциям ИИ для одного сообщения пользователя."""

    telegram_id: int
    user_text: str
    notes: list[dict]
    tz: ZoneInfo
    now: datetime
    # Отправить пользователю таблицу оценок (как /grades).
    show_grades: Callable[[], Awaitable[None]]
    # Свежий журнал из Platonus; None — Platonus не подключён.
    fetch_grades: Callable[[], Awaitable[list[dict] | None]]
    # Ответы о выполненных действиях — пишутся в историю.
    actions: list[str] = field(default_factory=list)
    # Пользователь уже получил ответ (таблицу и сводку),
    # короткую фразу ИИ вроде «таблица отправлена» можно не слать.
    reply_optional: bool = False
    # Отправить график прогресса; аргумент — предмет или None (все).
    show_chart: Callable[[str | None], Awaitable[str | None]] | None = None
    # Разговор шёл об оценках — под ответом стоит предложить график.
    offer_chart: bool = False


async def execute_tool(ctx: ToolContext, name: str, arguments: str) -> dict:
    handler = HANDLERS.get(name)

    if handler is None:
        return {"error": f"Функция {name} недоступна."}

    model, function = handler

    try:
        args = model.model_validate_json(arguments or "{}")
    except ValidationError:
        return {"error": "Неверные параметры. Уточни запрос у пользователя."}

    try:
        return await function(ctx, args)
    except ToolError as error:
        return {"error": str(error)}
    except DatabaseError:
        return {"error": "Ошибка базы данных. Попробуй позже."}


async def show_grades(ctx: ToolContext, args: NoArgs) -> dict:
    await ctx.show_grades()
    ctx.actions.append("Отправил таблицу и сводку оценок.")
    ctx.reply_optional = True
    return {
        "ok": True,
        "info": (
            "Таблица оценок и краткая сводка уже отправлены пользователю. "
            "Если он не задал другого вопроса, ничего не добавляй."
        ),
    }


async def get_schedule(ctx: ToolContext, args: ScheduleArgs) -> dict:
    today = ctx.now.date()

    if args.day == "today":
        days = [today]
    elif args.day == "tomorrow":
        days = [today + timedelta(days=1)]
    elif args.day == "week":
        monday = today - timedelta(days=today.weekday())
        days = [monday + timedelta(days=offset) for offset in range(7)]
    else:
        try:
            days = [date.fromisoformat(args.day)]
        except ValueError:
            raise ToolError("day: today, tomorrow, week или дата YYYY-MM-DD.")

    try:
        schedule = await load_schedule(ctx.telegram_id)
    except RuntimeError as error:
        raise ToolError(str(error))
    except Exception:
        raise ToolError("Не удалось загрузить расписание из Platonus. Попробуй позже.")

    if schedule is None:
        raise ToolError("Platonus не подключён. Нужна команда /connect.")

    return {
        "today": today.isoformat(),
        "days": [
            {
                "date": day.isoformat(),
                "weekday": day.isoweekday(),
                "week_of_semester": week_number(schedule, day),
                "lessons": lessons_for_ai(schedule, day),
            }
            for day in days
        ],
    }


async def show_grade_chart(ctx: ToolContext, args: ChartArgs) -> dict:
    if ctx.show_chart is None:
        raise ToolError("График сейчас недоступен.")

    try:
        subject = await ctx.show_chart(args.subject)
    except UnknownSubject as error:
        raise ToolError(
            "Такого предмета нет. Предметы в журнале: "
            + "; ".join(error.subjects)
        )

    ctx.actions.append(f"Отправил график прогресса{f': {subject}' if subject else ''}.")
    ctx.reply_optional = True
    return {
        "ok": True,
        "subject": subject,
        "info": "График уже отправлен пользователю картинкой.",
    }


async def get_grades(ctx: ToolContext, args: GetGradesArgs) -> dict:
    ctx.offer_chart = True
    snapshot = None

    if not args.refresh:
        snapshot = await asyncio.to_thread(
            database.get_grade_snapshot,
            ctx.telegram_id,
        )

    if snapshot is None:
        grades = await ctx.fetch_grades()

        if grades is None:
            raise ToolError("Platonus не подключён. Нужна команда /connect.")

        fetched_at = ctx.now
    else:
        grades, fetched_at = snapshot

    return {
        "fetched_at": local_time(fetched_at, ctx.tz),
        "grades": compact_grades(grades),
    }


async def get_grade_changes(ctx: ToolContext, args: GradeChangesArgs) -> dict:
    ctx.offer_chart = True
    changes = await asyncio.to_thread(
        database.get_grade_changes_since,
        ctx.telegram_id,
        args.days,
    )

    for change in changes:
        change["detected_at"] = local_time(change["detected_at"], ctx.tz)

    return {"days": args.days, "changes": changes}


async def save_note(ctx: ToolContext, args: SaveNoteArgs) -> dict:
    if args.url is not None and args.url not in ctx.user_text:
        raise ToolError("Ссылки нет в сообщении пользователя. Не придумывай её.")

    remind_at = parse_remind_at(args.remind_at, ctx.tz, ctx.now)

    await asyncio.to_thread(database.create_profile, ctx.telegram_id)
    note_id = await asyncio.to_thread(
        database.save_note,
        telegram_id=ctx.telegram_id,
        topic=args.topic,
        original_text=ctx.user_text,
        url=args.url,
        remind_at=remind_at,
    )

    ctx.actions.append(f"Сохранил заметку: {args.topic}.")
    return {
        "ok": True,
        "note_id": note_id,
        "remind_at": local_time(remind_at, ctx.tz),
    }


async def find_notes(ctx: ToolContext, args: SearchNotesArgs) -> dict:
    found = search_notes(ctx.notes, args.query)
    return {"notes": [note_for_ai(note, ctx.tz) for note in found]}


def _own_note(ctx: ToolContext, note_id: int) -> dict:
    note = next((note for note in ctx.notes if note["id"] == note_id), None)

    if note is None:
        raise ToolError("У пользователя нет заметки с таким id.")

    return note


async def delete_note(ctx: ToolContext, args: DeleteNoteArgs) -> dict:
    note = _own_note(ctx, args.note_id)

    deleted = await asyncio.to_thread(
        database.delete_note,
        ctx.telegram_id,
        args.note_id,
    )

    if not deleted:
        raise ToolError("Этой заметки уже нет в базе.")

    ctx.notes.remove(note)
    ctx.actions.append(f"Удалил заметку: {note['topic']}.")
    return {"ok": True, "deleted": note["topic"]}


async def update_note(ctx: ToolContext, args: UpdateNoteArgs) -> dict:
    note = _own_note(ctx, args.note_id)

    if args.url != note["url"] and (
        args.url is None or args.url not in ctx.user_text
    ):
        raise ToolError(
            "Ссылку можно заменить только на присланную пользователем. "
            "Если ссылку не просили менять, передай прежнюю."
        )

    if args.remind_at == local_time(note["remind_at"], ctx.tz):
        # Прежнее время сохраняем как есть, даже если оно прошло.
        remind_at = note["remind_at"]
    else:
        remind_at = parse_remind_at(args.remind_at, ctx.tz, ctx.now)

    updated = await asyncio.to_thread(
        database.update_note,
        ctx.telegram_id,
        args.note_id,
        args.topic,
        args.original_text,
        args.url,
        remind_at,
    )

    if not updated:
        raise ToolError("Этой заметки уже нет в базе.")

    note.update(
        topic=args.topic,
        original_text=args.original_text,
        url=args.url,
        remind_at=remind_at,
    )
    ctx.actions.append(f"Обновил заметку: {args.topic}.")
    return {"ok": True, "remind_at": local_time(remind_at, ctx.tz)}


HANDLERS = {
    "show_grades": (NoArgs, show_grades),
    "get_grades": (GetGradesArgs, get_grades),
    "get_grade_changes": (GradeChangesArgs, get_grade_changes),
    "show_grade_chart": (ChartArgs, show_grade_chart),
    "get_schedule": (ScheduleArgs, get_schedule),
    "save_note": (SaveNoteArgs, save_note),
    "search_notes": (SearchNotesArgs, find_notes),
    "delete_note": (DeleteNoteArgs, delete_note),
    "update_note": (UpdateNoteArgs, update_note),
}

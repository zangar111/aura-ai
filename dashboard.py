"""Данные для Mini App: журнал, изменения и заметки одного пользователя."""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import DEFAULT_LANGUAGE, DEFAULT_TIMEZONE
from database import (
    get_grade_changes_since,
    get_grade_snapshot,
    get_language,
    get_notes,
    get_schedule,
    get_timezone,
)
from grade_changes import is_important
from grade_chart import weekly_series
from grade_summary import compact_grades
from schedule import week_number

CHANGES_DAYS = 30


def _timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def _iso(moment, tz: ZoneInfo) -> str | None:
    return moment.astimezone(tz).isoformat(timespec="minutes") if moment else None


def build_subjects(grades: list[dict]) -> tuple[list[dict], int]:
    """Предметы с недельными баллами и итоговыми столбцами."""
    series = weekly_series(grades)
    totals = {}

    for row in compact_grades(grades):
        totals.setdefault(row["subject"], {})[row["type"]] = row["totals"]

    subjects = []
    last_week = 15

    for name, by_type in series.items():
        numbers = [
            value
            for marks in by_type.values()
            for value in marks.values()
            if isinstance(value, float)
        ]
        absences = sum(
            1 for marks in by_type.values() for value in marks.values() if value == "absent"
        )

        for marks in by_type.values():
            last_week = max([last_week, *marks])

        subjects.append(
            {
                "name": name,
                "average": round(sum(numbers) / len(numbers), 1) if numbers else None,
                "absences": absences,
                "types": [
                    {
                        "type": lesson_type,
                        "weeks": {str(week): value for week, value in sorted(marks.items())},
                        "totals": totals.get(name, {}).get(lesson_type, {}),
                    }
                    for lesson_type, marks in by_type.items()
                ],
            }
        )

    return subjects, last_week


def _load(telegram_id: int) -> dict:
    language = get_language(telegram_id) or DEFAULT_LANGUAGE
    tz = _timezone(get_timezone(telegram_id))
    snapshot = get_grade_snapshot(telegram_id)

    if snapshot is not None:
        grades, fetched_at = snapshot
        subjects, last_week = build_subjects(grades)
    else:
        fetched_at, subjects, last_week = None, [], 15

    changes = [
        {
            "subject": change["subject"],
            "type": change["stream"].rsplit("-", 1)[-1].strip(),
            "column": change["column"],
            "old": change["old_value"],
            "new": change["new_value"],
            "kind": change["kind"],
            "at": _iso(change["detected_at"], tz),
        }
        for change in get_grade_changes_since(telegram_id, CHANGES_DAYS)
        # Пересчёты ТК и рейтинга в ленте изменений только мешают.
        if is_important(change["column"])
    ]

    notes = [
        {
            "id": note["id"],
            "topic": note["topic"],
            "url": note["url"],
            "text": note["original_text"],
            "remind_at": _iso(note.get("remind_at"), tz),
        }
        for note in get_notes(telegram_id)
    ]

    stored_schedule = get_schedule(telegram_id)
    schedule = stored_schedule[0] if stored_schedule is not None else None
    today = datetime.now(tz).date()

    return {
        "language": language if language in ("kk", "ru") else DEFAULT_LANGUAGE,
        "today": today.isoformat(),
        "schedule": schedule and {
            "days": schedule["days"],
            "semester_start": schedule.get("semester_start"),
            "semester_end": schedule.get("semester_end"),
            "week": week_number(schedule, today),
        },
        "has_grades": snapshot is not None,
        "fetched_at": _iso(fetched_at, tz),
        "last_week": last_week,
        "subjects": subjects,
        "changes": changes,
        "notes": notes,
    }


async def load_dashboard(telegram_id: int) -> dict:
    return await asyncio.to_thread(_load, telegram_id)

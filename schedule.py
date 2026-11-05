"""Расписание занятий: разбор ответа Platonus, поиск пар, оформление."""

import re
from datetime import date, datetime, timedelta
from html import escape

# Сколько минут перерыва между парами считается «подряд»
# (в ЕНУ большой перерыв после 3-й пары — 20 минут).
MERGE_GAP_MINUTES = 20

TYPE_NAMES = {
    "kk": {"L": "Дәріс", "Lab": "Зертхана", "Pr": "Практика", "SRO": "СӨЖ"},
    "ru": {"L": "Лекция", "Lab": "Лабораторная", "Pr": "Практика", "SRO": "СРО"},
}

WEEKDAYS = {
    "kk": ["дүйсенбі", "сейсенбі", "сәрсенбі", "бейсенбі", "жұма", "сенбі", "жексенбі"],
    "ru": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
}

MONTHS = {
    "kk": ["қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым",
           "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
}

TEXTS = {
    "kk": {
        "today": "Бүгін",
        "tomorrow": "Ертең",
        "week": "{n}-апта",
        "no_lessons": "Сабақ жоқ 🎉",
        "online": "онлайн",
        "join": "Teams арқылы қосылу",
        "room": "{room} ауд.",
    },
    "ru": {
        "today": "Сегодня",
        "tomorrow": "Завтра",
        "week": "{n}-я неделя",
        "no_lessons": "Пар нет 🎉",
        "online": "онлайн",
        "join": "подключиться в Teams",
        "room": "ауд. {room}",
    },
}


def _language(language: str) -> str:
    return language if language in TEXTS else "kk"


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")[:2]
    return int(hours) * 60 + int(minutes)


def short_building(building: str | None) -> str | None:
    """«B02. №2 Оқу ғимараты (АТФ)» → «B02 (АТФ)»."""
    if not building:
        return None

    code = building.split(".", 1)[0].strip()
    abbreviation = re.search(r"\(([^)]+)\)\s*$", building)

    if abbreviation and code != building:
        return f"{code} ({abbreviation.group(1)})"

    return building.strip()


def _lesson_type(lesson: dict) -> str:
    suffix = (lesson.get("studygroupShortName") or "").rsplit("-", 1)[-1].strip()

    if suffix in ("L", "Lab", "Pr", "SRO"):
        return suffix

    short = (lesson.get("groupTypeShortName") or "").lower()
    return {"лек": "L", "лаб": "Lab", "прак": "Pr", "пр": "Pr"}.get(short, suffix or short)


def _merge(lessons: list[dict]) -> list[dict]:
    """Склеивает пары одного занятия, идущие подряд в одном месте."""
    merged = []
    same = ("subject", "type", "room", "building", "online", "link")

    for lesson in sorted(lessons, key=lambda item: item["start"]):
        previous = merged[-1] if merged else None

        if (
            previous is not None
            and all(previous[key] == lesson[key] for key in same)
            and 0 <= _minutes(lesson["start"]) - _minutes(previous["finish"]) <= MERGE_GAP_MINUTES
        ):
            previous["finish"] = lesson["finish"]
            previous["pairs"] += 1
            continue

        merged.append({**lesson, "pairs": 1})

    return merged


def normalize(raw: dict) -> dict:
    """Ответ Platonus /userSchedule/student/... → компактное расписание."""
    hours = {hour["number"]: hour for hour in raw["lessonHours"]}
    days = {}

    for day_key, day in raw["timetable"]["days"].items():
        lessons = []

        for number, slot in day["lessons"].items():
            hour = hours.get(int(number))

            if hour is None:
                continue

            for lesson in slot["lessons"]:
                if lesson.get("empty"):
                    continue

                links = lesson.get("links") or []
                lessons.append(
                    {
                        "start": hour["start"][:5],
                        "finish": hour["finish"][:5],
                        "subject": " ".join((lesson.get("subjectName") or "").split()),
                        "type": _lesson_type(lesson),
                        "type_name": lesson.get("groupTypeFullName"),
                        "tutor": (lesson.get("tutorShortName") or lesson.get("tutorName") or "").strip(),
                        "room": lesson.get("auditory"),
                        "building": short_building(lesson.get("building")),
                        "online": bool(lesson.get("onlineClass")),
                        "link": lesson.get("webinarLink") or (links[0] if links else None),
                    }
                )

        days[str(int(day_key))] = _merge(lessons)

    return {
        "days": days,
        "week": raw.get("activeWeekNumber"),
        "weeks_total": len(raw.get("weekList") or []) or None,
        "semester_start": raw.get("startSemesterPeriod"),
        "semester_end": raw.get("finishSemesterPeriod"),
    }


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def in_semester(schedule: dict, day: date) -> bool:
    start = _parse_date(schedule.get("semester_start"))
    end = _parse_date(schedule.get("semester_end"))
    return (start is None or day >= start) and (end is None or day <= end)


def lessons_on(schedule: dict, day: date) -> list[dict]:
    """Пары на дату. Расписание одинаковое каждую неделю семестра.

    В ответе Platonus день 1 — понедельник (сверено с расписанием ЕНУ).
    """
    if not in_semester(schedule, day):
        return []

    return schedule["days"].get(str(day.isoweekday()), [])


def week_number(schedule: dict, day: date) -> int | None:
    start = _parse_date(schedule.get("semester_start"))

    if start is None:
        return schedule.get("week")

    monday = start - timedelta(days=start.weekday())
    return (day - monday).days // 7 + 1


def lesson_start(lesson: dict, day: date, tz) -> datetime:
    hours, minutes = lesson["start"].split(":")
    return datetime(day.year, day.month, day.day, int(hours), int(minutes), tzinfo=tz)


def format_date(day: date, language: str) -> str:
    language = _language(language)
    return f"{WEEKDAYS[language][day.weekday()]}, {day.day} {MONTHS[language][day.month - 1]}"


def format_lesson(lesson: dict, language: str) -> str:
    language = _language(language)
    texts = TEXTS[language]
    type_name = TYPE_NAMES[language].get(lesson["type"]) or lesson.get("type_name") or ""
    details = [type_name]

    if lesson.get("tutor"):
        details.append(lesson["tutor"])

    if lesson["online"]:
        place = f"💻 {texts['online']}"

        if lesson.get("link"):
            place += f" · <a href=\"{escape(lesson['link'])}\">{texts['join']}</a>"
    else:
        parts = []

        if lesson.get("room"):
            parts.append(texts["room"].format(room=lesson["room"]))

        if lesson.get("building"):
            parts.append(lesson["building"])

        place = "📍 " + ", ".join(escape(part) for part in parts) if parts else ""

    lines = [
        f"<b>{lesson['start']}–{lesson['finish']}</b>  {escape(lesson['subject'])}",
        "      " + " · ".join(escape(part) for part in details if part),
    ]

    if place:
        lines.append("      " + place)

    return "\n".join(lines)


def format_day(schedule: dict, day: date, language: str, label: str | None = None) -> str:
    """Расписание дня в HTML для Telegram."""
    language = _language(language)
    texts = TEXTS[language]
    title = f"📅 <b>{label + ', ' if label else ''}{format_date(day, language)}</b>"
    week = week_number(schedule, day)

    if week and in_semester(schedule, day):
        title += f" · {texts['week'].format(n=week)}"

    lessons = lessons_on(schedule, day)

    if not lessons:
        return f"{title}\n{texts['no_lessons']}"

    return title + "\n\n" + "\n\n".join(format_lesson(lesson, language) for lesson in lessons)


def format_week(schedule: dict, monday: date, language: str) -> str:
    """Неделя: только дни, в которые есть пары."""
    parts = [
        format_day(schedule, monday + timedelta(days=offset), language)
        for offset in range(7)
        if lessons_on(schedule, monday + timedelta(days=offset))
    ]
    return "\n\n".join(parts) or TEXTS[_language(language)]["no_lessons"]


def lessons_for_ai(schedule: dict, day: date) -> list[dict]:
    return [
        {key: lesson.get(key) for key in (
            "start", "finish", "subject", "type", "tutor", "room", "building", "online", "link",
        )}
        for lesson in lessons_on(schedule, day)
    ]

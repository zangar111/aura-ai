"""Демо-данные для съёмки видео: выдуманный студент, без реальных оценок.

Используется генератором сообщений (build_messages.py) и предпросмотром
Mini App (serve_miniapp.py). Все имена и баллы придуманы.
"""

from datetime import date

TODAY = date(2026, 11, 5)  # четверг, 10-я неделя

SUBJECTS = {
    "Терең оқыту": "DL 3-1",
    "Блокчейн технологиялары": "BT 3-2",
    "Деректер қоймасы": "DW 3-1",
    "Веб-бағдарламалау": "WEB 3-1",
    "Ықтималдықтар теориясы": "PT 3-3",
}

# Баллы по неделям 1..9 для каждого типа занятия. "н.п." — пропуск.
WEEKS = {
    ("Терең оқыту", "L"): ["90", "85", "88", "92", "н.п.", "90", "94", "91", "95"],
    ("Терең оқыту", "Lab"): ["80", "85", "90", "88", "92", "95", "93", "96", "98"],
    ("Блокчейн технологиялары", "L"): ["70", "65", "н.п.", "60", "55", "н.п.", "62", "58", "52"],
    ("Блокчейн технологиялары", "Lab"): ["75", "70", "68", "60", "н.п.", "55", "60", "50", "48"],
    ("Деректер қоймасы", "L"): ["85", "88", "90", "86", "89", "91", "90", "93", "92"],
    ("Деректер қоймасы", "SRO"): ["80", "82", "85", "", "88", "90", "", "92", "94"],
    ("Веб-бағдарламалау", "Lab"): ["95", "98", "100", "96", "100", "98", "99", "100", "100"],
    ("Ықтималдықтар теориясы", "L"): ["78", "72", "80", "75", "70", "68", "74", "71", "76"],
    ("Ықтималдықтар теориясы", "SRO"): ["70", "75", "", "72", "68", "", "70", "73", "75"],
}

TOTALS = {
    "Терең оқыту": {"ТК1": "91", "РК1": "94", "Р1": "92"},
    "Блокчейн технологиялары": {"ТК1": "61", "РК1": "48", "Р1": "55"},
    "Деректер қоймасы": {"ТК1": "88", "РК1": "90", "Р1": "89"},
    "Веб-бағдарламалау": {"ТК1": "98", "РК1": "97", "Р1": "98"},
    "Ықтималдықтар теориясы": {"ТК1": "73", "РК1": "70", "Р1": "72"},
}


def grades() -> list[dict]:
    rows = []

    for (subject, lesson_type), marks in WEEKS.items():
        row_marks = {str(week): value for week, value in enumerate(marks, start=1)}
        row_marks.update({str(week): "" for week in range(10, 16)})
        row_marks.update(TOTALS[subject])
        rows.append(
            {
                "subject": subject,
                "stream": f"{SUBJECTS[subject]}-{lesson_type}",
                "marks": row_marks,
            }
        )

    return rows


def _lesson(subject, short_type, tutor, *, room=None, building=None, online=False):
    full = {
        "L": ("лек", "Дәріс"),
        "Lab": ("лаб", "Зертханалық жұмыстар"),
        "Pr": ("прак", "Практикалық сабақ"),
    }[short_type]
    return {
        "subjectName": subject,
        "studygroupShortName": f"{SUBJECTS[subject]}-{short_type}",
        "groupTypeShortName": full[0],
        "groupTypeFullName": full[1],
        "tutorShortName": tutor,
        "auditory": None if online else room,
        "building": None if online else building,
        "onlineClass": online,
        "webinarLink": "https://teams.microsoft.com/l/meetup-join/demo" if online else None,
        "links": [],
        "empty": False,
        "weekNumber": 0,
    }


MAIN = "B01. №1 Бас оқу ғимараты (БОҒ)"
IT = "B02. №2 Оқу ғимараты (АТФ)"


def raw_schedule() -> dict:
    """Ответ в формате Platonus /userSchedule/student/..."""
    slot = lambda *lessons: {"lessons": list(lessons)}  # noqa: E731

    return {
        "activeWeekNumber": 10,
        "startSemesterPeriod": "2026-09-01",
        "finishSemesterPeriod": "2026-12-19",
        "weekList": list(range(1, 16)),
        "lessonHours": [
            {"number": 1, "start": "09:00:00", "finish": "09:50:00"},
            {"number": 2, "start": "10:00:00", "finish": "10:50:00"},
            {"number": 3, "start": "11:10:00", "finish": "12:00:00"},
            {"number": 4, "start": "12:10:00", "finish": "13:00:00"},
            {"number": 5, "start": "14:00:00", "finish": "14:50:00"},
            {"number": 6, "start": "18:10:00", "finish": "19:00:00"},
        ],
        "timetable": {
            "days": {
                "1": {"lessons": {
                    "1": slot(_lesson("Деректер қоймасы", "L", "Әбенова Г.С.", room="305", building=MAIN)),
                    "2": slot(_lesson("Ықтималдықтар теориясы", "Pr", "Нұрланов Д.Е.", room="214", building=MAIN)),
                }},
                "2": {"lessons": {
                    "3": slot(_lesson("Веб-бағдарламалау", "Lab", "Касымов А.Т.", room="410", building=IT)),
                    "4": slot(_lesson("Веб-бағдарламалау", "Lab", "Касымов А.Т.", room="410", building=IT)),
                }},
                "3": {"lessons": {
                    "1": slot(_lesson("Блокчейн технологиялары", "L", "Серікова Н.А.", room="512", building=IT)),
                    "6": slot(_lesson("Ықтималдықтар теориясы", "L", "Нұрланов Д.Е.", online=True)),
                }},
                "4": {"lessons": {
                    "2": slot(_lesson("Терең оқыту", "L", "Жақыпов Е.М.", room="710", building=IT)),
                    "3": slot(_lesson("Терең оқыту", "Lab", "Жақыпов Е.М.", room="106", building=IT)),
                    "4": slot(_lesson("Терең оқыту", "Lab", "Жақыпов Е.М.", room="106", building=IT)),
                    "6": slot(_lesson("Блокчейн технологиялары", "L", "Серікова Н.А.", online=True)),
                }},
                "5": {"lessons": {
                    "1": slot(_lesson("Блокчейн технологиялары", "Lab", "Серікова Н.А.", room="508", building=IT)),
                    "2": slot(_lesson("Блокчейн технологиялары", "Lab", "Серікова Н.А.", room="508", building=IT)),
                    "5": slot(_lesson("Деректер қоймасы", "L", "Әбенова Г.С.", room="305", building=MAIN)),
                }},
            }
        },
    }

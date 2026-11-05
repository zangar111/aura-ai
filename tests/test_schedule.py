import asyncio
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import assistant_tools
import schedule_service
from schedule import format_day, lessons_on, normalize, short_building, week_number
from test_assistant_tools import make_ctx

TZ = ZoneInfo("Asia/Almaty")
FRIDAY = date(2026, 10, 23)


def lesson(subject, short_type, *, online=False, room="710", building="B02. №2 Оқу ғимараты (АТФ)"):
    return {
        "subjectName": subject,
        "studygroupShortName": f"XX 1-{short_type}",
        "groupTypeShortName": "лек" if short_type == "L" else "лаб",
        "groupTypeFullName": "Дәріс" if short_type == "L" else "Лабораториялық жұмыстар",
        "tutorShortName": "Серікова Н.А.",
        "auditory": None if online else room,
        "building": None if online else building,
        "onlineClass": online,
        "webinarLink": "https://teams.example/meet/1" if online else None,
        "links": [],
        "empty": False,
        "weekNumber": 0,
    }


RAW = {
    "activeWeekNumber": 8,
    "startSemesterPeriod": "2026-09-01",
    "finishSemesterPeriod": "2026-12-12",
    "weekList": list(range(1, 16)),
    "lessonHours": [
        {"number": 1, "start": "09:00:00", "finish": "09:50:00"},
        {"number": 2, "start": "10:00:00", "finish": "10:50:00"},
        {"number": 3, "start": "11:10:00", "finish": "12:00:00"},
        {"number": 4, "start": "18:10:00", "finish": "19:00:00"},
    ],
    "timetable": {
        "days": {
            "1": {"lessons": {"1": {"lessons": []}}},
            "5": {
                "lessons": {
                    "1": {"lessons": [lesson("Деректерді өңдеу", "L")]},
                    "2": {"lessons": [lesson("Терең оқыту", "Lab", room="106")]},
                    "3": {"lessons": [lesson("Терең оқыту", "Lab", room="106")]},
                    "4": {"lessons": [lesson("Блокчейн", "L", online=True)]},
                }
            },
        }
    },
}


def test_normalize_merges_pairs_in_a_row():
    friday = normalize(RAW)["days"]["5"]

    assert [(item["start"], item["finish"], item["subject"]) for item in friday] == [
        ("09:00", "09:50", "Деректерді өңдеу"),
        ("10:00", "12:00", "Терең оқыту"),  # перерыв 20 минут — одна запись
        ("18:10", "19:00", "Блокчейн"),
    ]
    assert friday[1]["pairs"] == 2
    assert friday[1]["type"] == "Lab"
    assert friday[2]["online"] and friday[2]["link"] == "https://teams.example/meet/1"


def test_short_building():
    assert short_building("B02. №2 Оқу ғимараты (АТФ)") == "B02 (АТФ)"
    assert short_building(None) is None
    assert short_building("Главный корпус") == "Главный корпус"


def test_lessons_by_date_and_semester_bounds():
    schedule = normalize(RAW)
    assert len(lessons_on(schedule, FRIDAY)) == 3
    assert lessons_on(schedule, date(2026, 10, 19)) == []  # понедельник пустой
    assert lessons_on(schedule, date(2027, 1, 15)) == []  # после семестра
    assert week_number(schedule, FRIDAY) == 8


def test_format_day_kk_and_ru():
    schedule = normalize(RAW)
    kk = format_day(schedule, FRIDAY, "kk", "Бүгін")
    ru = format_day(schedule, FRIDAY, "ru", "Сегодня")

    assert kk.startswith("📅 <b>Бүгін, жұма, 23 қазан</b> · 8-апта")
    assert "Зертхана · Серікова Н.А." in kk
    assert "📍 106 ауд., B02 (АТФ)" in kk
    assert '<a href="https://teams.example/meet/1">Teams арқылы қосылу</a>' in kk
    assert "пятница, 23 октября" in ru and "ауд. 710" in ru
    assert "Сабақ жоқ" in format_day(schedule, date(2026, 10, 19), "kk")


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append(text)


def recipient(**overrides):
    return {
        "telegram_id": 5,
        "timezone_name": "Asia/Almaty",
        "language_code": "kk",
        "digest_enabled": True,
        "digest_time": time(7, 30),
        "lesson_reminders": True,
        "last_digest_on": None,
        "schedule": normalize(RAW),
        **overrides,
    }


def run_at(monkeypatch, moment: datetime, rec: dict) -> list[str]:
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment

    monkeypatch.setattr(schedule_service, "datetime", FrozenDatetime)
    monkeypatch.setattr(schedule_service, "get_notes_due_between", lambda *args: [
        {"topic": "Лаба 1С", "remind_at": datetime(2026, 10, 23, 14, 0, tzinfo=TZ)},
    ])
    monkeypatch.setattr(schedule_service, "get_grade_changes_since", lambda *args: [
        {"subject": "Блокчейн", "column": "7", "new_value": "90"},
    ])
    marked = []
    monkeypatch.setattr(schedule_service, "mark_digest_sent", lambda telegram_id, day: marked.append(day))

    bot = FakeBot()
    asyncio.run(schedule_service._process_recipient(bot, rec))
    return bot.sent, marked


def test_digest_sent_once_at_chosen_time(monkeypatch):
    schedule_service._sent_lesson_reminders.clear()
    sent, marked = run_at(monkeypatch, datetime(2026, 10, 23, 7, 31, tzinfo=TZ), recipient())

    assert len(sent) == 1 and marked == [FRIDAY]
    digest = sent[0]
    assert "Қайырлы таң" in digest and "Бүгінгі сабақтар</b> (3)" in digest
    assert "Бірінші сабақ — 09:00" in digest
    assert "14:00 — Лаба 1С" in digest
    assert "Блокчейн · 7-апта: <b>90</b>" in digest

    # Уже отправлен сегодня — второй раз не шлём.
    sent, _ = run_at(monkeypatch, datetime(2026, 10, 23, 7, 40, tzinfo=TZ), recipient(last_digest_on=FRIDAY))
    assert sent == []


def test_no_digest_before_time_or_when_disabled(monkeypatch):
    assert run_at(monkeypatch, datetime(2026, 10, 23, 7, 0, tzinfo=TZ), recipient())[0] == []
    assert run_at(monkeypatch, datetime(2026, 10, 23, 7, 45, tzinfo=TZ), recipient(digest_enabled=False))[0] == []
    # Бот был выключен утром — днём дайджест уже не нужен.
    assert run_at(monkeypatch, datetime(2026, 10, 23, 13, 0, tzinfo=TZ), recipient(lesson_reminders=False))[0] == []


def test_lesson_reminder_15_minutes_before(monkeypatch):
    schedule_service._sent_lesson_reminders.clear()
    rec = recipient(digest_enabled=False)

    sent, _ = run_at(monkeypatch, datetime(2026, 10, 23, 9, 50, tzinfo=TZ), rec)
    assert len(sent) == 1
    assert sent[0].startswith("⏰ <b>10 минуттан кейін сабақ:</b>")
    assert "Терең оқыту" in sent[0]

    # Повторно о той же паре не напоминаем.
    assert run_at(monkeypatch, datetime(2026, 10, 23, 9, 52, tzinfo=TZ), rec)[0] == []
    # Слишком рано — ещё не напоминаем.
    assert run_at(monkeypatch, datetime(2026, 10, 23, 17, 40, tzinfo=TZ), rec)[0] == []


def test_ai_schedule_tool(monkeypatch):
    async def fake_load(telegram_id, refresh=False):
        return normalize(RAW)

    monkeypatch.setattr(assistant_tools, "load_schedule", fake_load)
    ctx = make_ctx()  # «сейчас» в тестах — 22.10.2026, четверг

    result = asyncio.run(assistant_tools.execute_tool(ctx, "get_schedule", '{"day": "tomorrow"}'))
    [day] = result["days"]
    assert day["date"] == "2026-10-23" and day["week_of_semester"] == 8
    assert [item["subject"] for item in day["lessons"]] == ["Деректерді өңдеу", "Терең оқыту", "Блокчейн"]

    week = asyncio.run(assistant_tools.execute_tool(ctx, "get_schedule", '{"day": "week"}'))
    assert len(week["days"]) == 7

    bad = asyncio.run(assistant_tools.execute_tool(ctx, "get_schedule", '{"day": "someday"}'))
    assert "error" in bad

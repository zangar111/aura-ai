"""Собирает тексты сообщений бота настоящими функциями проекта.

Запуск из корня репозитория:
    python video/raw/build_messages.py

Результат: video/raw/build/messages.json и chart.png — их читает
сцена telegram.html. Данные — из demo_data.py (выдуманные).
"""

import json
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))

import demo_data  # noqa: E402
from grade_chart import render_progress_chart  # noqa: E402
from grades_service import (  # noqa: E402
    CHART_TEXTS,
    format_grade_changes,
    render_grade_summary,
)
from schedule import format_date, format_day, format_lesson, lessons_on, normalize, week_number  # noqa: E402
from schedule_service import TEXTS as SCHEDULE_TEXTS  # noqa: E402
from streaming import STATUSES  # noqa: E402

OUT = HERE / "build"
LANG = "kk"


def change(subject, lesson_type, column, new, old="", kind="new"):
    return {
        "subject": subject,
        "stream": f"{demo_data.SUBJECTS[subject]}-{lesson_type}",
        "column": column,
        "old_value": old,
        "new_value": new,
        "kind": kind,
    }


def main():
    OUT.mkdir(exist_ok=True)
    grades = demo_data.grades()
    schedule = normalize(demo_data.raw_schedule())
    today = demo_data.TODAY
    texts = SCHEDULE_TEXTS[LANG]

    notification, _ = format_grade_changes(
        [
            change("Блокчейн технологиялары", "L", "9", "52"),
            change("Блокчейн технологиялары", "Lab", "9", "48"),
            change("Блокчейн технологиялары", "L", "РК1", "48"),
            change("Терең оқыту", "Lab", "9", "98"),
        ],
        LANG,
    )

    summary = render_grade_summary(
        {
            "changes": [
                "Блокчейн: дәріс — 52, зертхана — 48, РК1 — 48",
                "Терең оқыту: зертхана — 98 🔥",
            ],
            "overall": "Қалған пәндер тұрақты: Терең оқыту мен Веб-бағдарламалау — 90+.",
            "risks": [
                "Блокчейн технологиялары — РК1 48, соңғы 4 аптада баллдар төмендеп келеді",
                "Блокчейн бойынша 3 сабақ босатылған (н.п.)",
            ],
            "tip": "Жұма күнгі блокчейн зертханасына дайындалып, "
                   "босатылған тапсырмаларды оқытушымен келісіп тапсырыңыз.",
        },
        LANG,
    )

    weak_answer = (
        "Ең нашар пәніңіз — <b>Блокчейн технологиялары</b> 📉\n\n"
        "• Орташа балл — <b>61</b> (басқа пәндерде 73-тен жоғары)\n"
        "• РК1 — <b>48</b>, бұл емтиханға жіберілу шегіне жақын\n"
        "• Соңғы 4 аптада баллдар 62 → 58 → 52 болып төмендеп келеді\n"
        "• 3 сабақ босатылған (н.п.)\n\n"
        "💡 <b>Не істеу керек:</b> жұма күні 09:00-де блокчейн зертханасы бар — "
        "босатылған 2 зертханалықты сол жерде тапсыруға болады. "
        "РК2-де 70+ алсаңыз, рейтинг 60-тан асады."
    )

    tomorrow = today + timedelta(days=1)
    tomorrow_lessons = lessons_on(schedule, tomorrow)
    tomorrow_answer = (
        f"Ертең, <b>{format_date(tomorrow, LANG)}</b>, {len(tomorrow_lessons)} сабақ бар:\n\n"
        "1️⃣ <b>09:00–10:50</b> Блокчейн технологиялары — зертхана, 508 ауд. (АТФ)\n"
        "2️⃣ <b>14:00–14:50</b> Деректер қоймасы — дәріс, 305 ауд. (БОҒ)\n\n"
        "Бірінші сабақ ерте басталады — 08:45-те еске саламын ⏰"
    )

    today_lessons = lessons_on(schedule, today)
    digest = (
        f"{texts['morning']}\n{texts['today']} — {format_date(today, LANG)}"
        f" · {texts['week'].format(n=week_number(schedule, today))}\n\n"
        + texts["lessons"].format(count=len(today_lessons))
        + "\n"
        + texts["first"].format(time=today_lessons[0]["start"])
        + "\n\n"
        + "\n\n".join(format_lesson(lesson, LANG) for lesson in today_lessons)
        + f"\n\n{texts['reminders']}\n• 18:00 — Терең оқыту: зертхана есебін жіберу"
        + f"\n\n{texts['grades'].format(count=4)}\n• Блокчейн технологиялары — 52, 48, РК1 48"
        + "\n• Терең оқыту — 98"
    )

    online = next(lesson for lesson in today_lessons if lesson["online"])
    reminder = texts["soon"].format(minutes=14) + "\n\n" + format_lesson(online, LANG)
    room_lesson = today_lessons[0]
    reminder_room = texts["soon"].format(minutes=15) + "\n\n" + format_lesson(room_lesson, LANG)

    messages = {
        "bot_name": "Aura",
        "bot_status": "бот",
        "notification": notification,
        "summary": summary,
        "chart_button": CHART_TEXTS[LANG]["button"],
        "chart_caption": CHART_TEXTS[LANG]["caption"].replace("\n", "<br>"),
        "statuses": STATUSES[LANG],
        "question_weak": "Ең нашар сабағым қайсы?",
        "answer_weak": weak_answer,
        "question_tomorrow": "ертең қандай сабақ бар?",
        "answer_tomorrow": tomorrow_answer,
        "digest": digest,
        "schedule_today": format_day(schedule, today, LANG, label="Бүгін"),
        "schedule_buttons": ["Бүгін", "Ертең", SCHEDULE_TEXTS[LANG]["week_button"]],
        "reminder_online": reminder,
        "reminder_room": reminder_room,
    }

    (OUT / "messages.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "chart.png").write_bytes(
        render_progress_chart(grades, LANG, subject="Блокчейн технологиялары")
    )
    (OUT / "chart_all.png").write_bytes(render_progress_chart(grades, LANG))
    (OUT / "grades.json").write_text(
        json.dumps(grades, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "schedule.json").write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK:", OUT)


if __name__ == "__main__":
    main()

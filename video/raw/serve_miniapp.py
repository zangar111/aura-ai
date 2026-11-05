"""Mini App на демо-данных для съёмки видео.

Запуск из корня репозитория:
    python video/raw/serve_miniapp.py

Открыть http://127.0.0.1:8090/preview (?scheme=dark — тёмная тема).
Это tools/webapp_preview.py, только журнал и расписание берутся
из demo_data.py, а не из grades.json и снимков Platonus.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import demo_data  # noqa: E402
import webapp_preview  # noqa: E402
from schedule import normalize  # noqa: E402

webapp_preview.sample_grades = demo_data.grades
webapp_preview.sample_schedule = lambda: normalize(demo_data.raw_schedule())

_sample_dashboard = webapp_preview.sample_dashboard


def sample_dashboard(language: str) -> dict:
    """Те же изменения, что в уведомлении из build_messages.py."""
    data = _sample_dashboard(language)
    now = datetime.fromisoformat(data["changes"][0]["at"]) + timedelta(hours=2)
    at = lambda hours: (now - timedelta(hours=hours)).isoformat(timespec="minutes")  # noqa: E731
    data["changes"] = [
        {"subject": "Блокчейн технологиялары", "type": "L", "column": "9", "old": "",
         "new": "52", "kind": "new", "at": at(0.4)},
        {"subject": "Блокчейн технологиялары", "type": "L", "column": "РК1", "old": "",
         "new": "48", "kind": "new", "at": at(0.4)},
        {"subject": "Блокчейн технологиялары", "type": "Lab", "column": "9", "old": "",
         "new": "48", "kind": "new", "at": at(0.4)},
        {"subject": "Терең оқыту", "type": "Lab", "column": "9", "old": "",
         "new": "98", "kind": "new", "at": at(0.4)},
        {"subject": "Деректер қоймасы", "type": "SRO", "column": "8", "old": "88",
         "new": "92", "kind": "updated", "at": at(26)},
    ]
    return data


webapp_preview.sample_dashboard = sample_dashboard

if __name__ == "__main__":
    asyncio.run(webapp_preview.main())

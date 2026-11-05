"""Предпросмотр Mini App в обычном браузере, без Telegram и без базы.

Запуск из корня проекта:
    python tools/webapp_preview.py

Затем открыть http://127.0.0.1:8090/preview
(можно добавить ?lang=ru и/или &scheme=dark).

Данные — примерные: журнал из grades.json (если есть) и выдуманные
изменения и заметки. Подпись Telegram делается тестовым токеном,
поэтому настоящий бот и настоящие пользователи не затрагиваются.
"""

import asyncio
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp import web  # noqa: E402

from config import ROOT  # noqa: E402
from dashboard import build_subjects  # noqa: E402
from schedule import normalize, week_number  # noqa: E402
from webapp_server import create_app  # noqa: E402

PORT = 8090
TOKEN = "123456:preview-token-not-a-real-bot"
TZ = ZoneInfo("Asia/Almaty")

THEMES = {
    "light": {
        "bg_color": "#ffffff", "secondary_bg_color": "#efeff3", "section_bg_color": "#ffffff",
        "text_color": "#000000", "hint_color": "#8e8e93", "link_color": "#2481cc",
        "button_color": "#2481cc", "button_text_color": "#ffffff",
    },
    "dark": {
        "bg_color": "#212d3b", "secondary_bg_color": "#151e27", "section_bg_color": "#212d3b",
        "text_color": "#ffffff", "hint_color": "#7d8b99", "link_color": "#5eabe1",
        "button_color": "#5288c1", "button_text_color": "#ffffff",
    },
}


def sign_init_data(language: str) -> str:
    """initData, подписанный так же, как это делает Telegram."""
    params = {
        "auth_date": str(int(time.time())),
        "query_id": "preview",
        "user": json.dumps(
            {"id": 1, "first_name": "Preview", "language_code": language},
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(params)


def sample_grades() -> list[dict]:
    path = ROOT / "grades.json"

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    return [
        {
            "subject": "Пример предмета",
            "stream": "EX 1-L",
            "marks": {"1": "90", "2": "н.п.", "3": "85", "ТК1": "80"},
        }
    ]


def sample_schedule() -> dict | None:
    """Расписание из снимка tools/capture_schedule.py, если он есть."""
    for path in sorted((ROOT / "debug" / "schedule").glob("*/responses.json"), reverse=True):
        for response in json.loads(path.read_text(encoding="utf-8")):
            if "/userSchedule/student/" in response["url"] and response["status"] == 200:
                return normalize(response["body"])

    return None


def sample_dashboard(language: str) -> dict:
    subjects, last_week = build_subjects(sample_grades())
    now = datetime.now(TZ)
    schedule = sample_schedule()
    first = subjects[0]["name"] if subjects else "Пример предмета"
    second = subjects[1]["name"] if len(subjects) > 1 else first

    return {
        "language": language,
        "today": now.date().isoformat(),
        "schedule": schedule and {
            "days": schedule["days"],
            "semester_start": schedule["semester_start"],
            "semester_end": schedule["semester_end"],
            "week": week_number(schedule, now.date()),
        },
        "has_grades": True,
        "fetched_at": (now - timedelta(minutes=12)).isoformat(timespec="minutes"),
        "last_week": last_week,
        "subjects": subjects,
        "changes": [
            {"subject": first, "type": "L", "column": "7", "old": "", "new": "90",
             "kind": "new", "at": (now - timedelta(hours=2)).isoformat(timespec="minutes")},
            {"subject": second, "type": "Lab", "column": "ТК1", "old": "78", "new": "96",
             "kind": "updated", "at": (now - timedelta(hours=3)).isoformat(timespec="minutes")},
            {"subject": second, "type": "SRO", "column": "5", "old": "50", "new": "",
             "kind": "removed", "at": (now - timedelta(days=1, hours=1)).isoformat(timespec="minutes")},
        ],
        "notes": [
            {"id": 1, "topic": "Лаба по 1С", "url": None,
             "text": "Напомни завтра в 9 про лабу по 1С, нужно сдать отчёт.",
             "remind_at": (now + timedelta(hours=18)).isoformat(timespec="minutes")},
            {"id": 2, "topic": "Блокчейн технологии — лекция", "url": "https://example.com/lecture",
             "text": "Сохрани ссылку на лекцию по блокчейну https://example.com/lecture",
             "remind_at": None},
        ],
    }


async def main():
    language_by_user = {"value": "kk"}

    async def load_dashboard(user_id: int) -> dict:
        return sample_dashboard(language_by_user["value"])

    app = create_app(TOKEN, load_dashboard)

    async def preview(request: web.Request) -> web.Response:
        language = "ru" if request.query.get("lang") == "ru" else "kk"
        scheme = "dark" if request.query.get("scheme") == "dark" else "light"
        language_by_user["value"] = language
        fragment = urlencode(
            {
                "tgWebAppData": sign_init_data(language),
                "tgWebAppVersion": "8.0",
                "tgWebAppPlatform": "weba",
                "tgWebAppThemeParams": json.dumps(THEMES[scheme]),
            },
            quote_via=quote,
        )
        # Не HTTP-редирект: aiohttp «нормализует» адрес и раскодирует
        # %26 и %3D внутри tgWebAppData, ломая подпись.
        return web.Response(
            # SDK Telegram запоминает тему в sessionStorage — сбрасываем,
            # чтобы ?scheme= переключал тему.
            text=(
                "<script>sessionStorage.clear();"
                f"location.replace('/#' + {json.dumps(fragment)});</script>"
            ),
            content_type="text/html",
        )

    app.router.add_get("/preview", preview)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start()
    print(f"Предпросмотр: http://127.0.0.1:{PORT}/preview", flush=True)

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())

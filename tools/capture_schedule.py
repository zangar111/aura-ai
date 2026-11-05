"""Снимок страницы расписания Platonus для разработки.

Запуск из корня проекта:
    python tools/capture_schedule.py

Скрипт входит в Platonus с PLATONUS_LOGIN и PLATONUS_PASSWORD из .env,
открывает расписание и сохраняет в debug/schedule/<время>/:
- screenshot.png — как выглядит страница;
- page.html — HTML страницы после загрузки;
- responses.json — данные (JSON), которые страница получила от сервера;
- requests.txt — список всех запросов страницы;
- storage.txt — названия (без значений) cookies и хранилищ браузера.

Что НЕ сохраняется: пароль, тела запросов, значения cookies и токенов,
ответы на запросы входа.
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

from config import ROOT  # noqa: E402
from parser import LOGIN_URL, is_logged_in_url  # noqa: E402

SCHEDULE_URL = "https://edu.enu.kz/v7/#/schedule/studentView"

# Сколько ждать, пока ты листаешь расписание (секунды).
BROWSE_SECONDS = 90

# Ответы на такие адреса могут содержать токены — их не сохраняем.
SECRET_URL = re.compile(r"login|logout|auth|token|password|session|captcha", re.I)
MAX_BODY_CHARS = 300_000


async def main():
    login = os.getenv("PLATONUS_LOGIN", "").strip()
    password = os.getenv("PLATONUS_PASSWORD", "")

    if not login or not password:
        raise SystemExit("Укажи PLATONUS_LOGIN и PLATONUS_PASSWORD в .env.")

    out_dir = ROOT / "debug" / "schedule" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    responses = []
    requests = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False, slow_mo=150)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        print("Вхожу в Platonus...")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.locator("#iin_input").fill(login)
        await page.locator("#pass_input").fill(password)
        await page.locator("#Submit1").click()

        print("Если появится капча или код — введи их в окне браузера (жду 2 минуты).")
        await page.wait_for_url(is_logged_in_url, wait_until="domcontentloaded", timeout=120_000)
        print("Вход выполнен.")

        # Запросы записываются только после входа.
        async def on_response(response):
            request = response.request
            url = response.url
            requests.append(f"{request.method} {response.status} {request.resource_type} {url}")

            if "edu.enu.kz" not in url or SECRET_URL.search(url):
                return

            if "json" not in (response.headers.get("content-type") or ""):
                return

            try:
                body = await response.text()
            except Exception:
                return

            try:
                data = json.loads(body)
            except ValueError:
                data = body[:MAX_BODY_CHARS]

            if len(body) > MAX_BODY_CHARS:
                data = {"_truncated": True, "_preview": body[:MAX_BODY_CHARS]}

            responses.append(
                {
                    "method": request.method,
                    "status": response.status,
                    "url": url,
                    "body": data,
                }
            )

        page.on("response", on_response)

        print("Открываю расписание...")
        await page.goto(SCHEDULE_URL, wait_until="domcontentloaded", timeout=60_000)

        try:
            await page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception:
            pass

        print(
            f"\nПолистай расписание в окне: другая неделя, другой день и т. п.\n"
            f"Через {BROWSE_SECONDS} секунд (или когда закроешь вкладку) "
            "всё сохранится."
        )

        try:
            await page.wait_for_event("close", timeout=BROWSE_SECONDS * 1000)
            closed = True
        except Exception:
            closed = False

        if not closed:
            await page.screenshot(path=str(out_dir / "screenshot.png"), full_page=True)
            (out_dir / "page.html").write_text(await page.content(), encoding="utf-8")

            storage = await page.evaluate(
                "() => ({local: Object.keys(localStorage), session: Object.keys(sessionStorage)})"
            )
            cookies = await context.cookies()
            (out_dir / "storage.txt").write_text(
                "cookies: " + ", ".join(sorted({c["name"] for c in cookies})) + "\n"
                "localStorage: " + ", ".join(storage["local"]) + "\n"
                "sessionStorage: " + ", ".join(storage["session"]) + "\n",
                encoding="utf-8",
            )

        await browser.close()

    (out_dir / "responses.json").write_text(
        json.dumps(responses, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "requests.txt").write_text("\n".join(requests), encoding="utf-8")

    print(f"\nГотово. Сохранено в {out_dir}")
    print(f"Ответов с данными: {len(responses)}, всего запросов: {len(requests)}")


if __name__ == "__main__":
    asyncio.run(main())

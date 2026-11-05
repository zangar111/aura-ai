import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import InvalidToken
from playwright.async_api import async_playwright, TimeoutError

from config import ROOT, SECRETS_DIR
from security import get_cipher

logger = logging.getLogger(__name__)

LOGIN_URL = "https://edu.enu.kz/"
JOURNAL_URL = (
    "https://edu.enu.kz/current_progress_gradebook_student?null"
)
SCHEDULE_URL = "https://edu.enu.kz/v7/#/schedule/studentView"
# Запрос, которым страница расписания получает данные.
SCHEDULE_API = "/rest/schedule/userSchedule/student/initial/"

SESSIONS_DIR = SECRETS_DIR / "sessions"

# 1 — показывать окно браузера: чтобы вручную пройти капчу
# или посмотреть, что происходит при проверке.
SHOW_BROWSER = os.getenv("PLATONUS_SHOW_BROWSER", "0") == "1"

# Пауза в миллисекундах перед каждым действием браузера,
# чтобы глазами успеть увидеть шаги. 0 — без пауз.
SLOW_MO = int(os.getenv("PLATONUS_SLOW_MO", "0") or 0)

# Снимки страницы при неудачной загрузке журнала.
DEBUG_DIR = ROOT / "debug"
DEBUG_KEEP_FILES = 40

JOURNAL_READY = """
() => {
    const table = document.querySelector("table.table-compact-2x");
    return table && table.rows.length > 2;
}
"""

EXTRACT_GRADES = """
() => {
    const table = document.querySelector("table.table-compact-2x");

    if (!table) {
        throw new Error("Таблица журнала не найдена");
    }

    const grid = [];

    Array.from(table.rows).forEach((row, rowIndex) => {
        grid[rowIndex] ??= [];
        let column = 0;

        for (const cell of row.cells) {
            while (grid[rowIndex][column] !== undefined) {
                column++;
            }

            for (let dy = 0; dy < cell.rowSpan; dy++) {
                grid[rowIndex + dy] ??= [];

                for (let dx = 0; dx < cell.colSpan; dx++) {
                    grid[rowIndex + dy][column + dx] =
                        cell.innerText.trim();
                }
            }

            column += cell.colSpan;
        }
    });

    const headers = grid[0].map((name, index) => {
        const lower = grid[1][index];

        return lower && lower !== name
            ? `${name} (${lower})`
            : name;
    });

    return grid.slice(2).map(row => ({
        subject: row[0],
        stream: row[1],
        marks: Object.fromEntries(
            headers.slice(3).map(
                (name, index) => [name, row[index + 3] ?? ""]
            )
        )
    }));
}
"""


def is_logged_in_url(url):
    return urlparse(url).path in {
        "/template.html",
        "/current_progress_gradebook_student",
    }


async def journal_is_open(page) -> bool:
    """Открывает журнал с сохранённой сессией. False — нужен вход."""
    try:
        await page.goto(
            JOURNAL_URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if not is_logged_in_url(page.url):
            return False

        await page.wait_for_function(JOURNAL_READY, timeout=15_000)
        return True
    except TimeoutError:
        return False


async def open_journal(page, login: str, password: str, *, interactive: bool = True):
    if not login or not password:
        raise ValueError("Логин и пароль Platonus не переданы.")

    logger.info("Выполняю автоматический вход в Platonus...")

    await page.goto(
        LOGIN_URL,
        wait_until="domcontentloaded",
        timeout=60_000,
    )

    # Селекторы проверены на форме Platonus ЕНУ.
    await page.locator("#iin_input").fill(login)
    await page.locator("#pass_input").fill(password)
    await page.locator("#Submit1").click()

    try:
        await page.wait_for_url(
            is_logged_in_url,
            wait_until="domcontentloaded",
            timeout=20_000,
        )

    except TimeoutError:
        if not interactive:
            raise
        logger.warning(
            "\nВход пока не завершён. Посмотри открытый браузер.\n"
            "Если нужен код подтверждения или капча, "
            "введи их там самостоятельно.\n"
            "Скрипт подождёт ещё 2 минуты."
        )

        await page.wait_for_url(
            is_logged_in_url,
            wait_until="domcontentloaded",
            timeout=120_000,
        )

    logger.info("Вход выполнен. Открываю журнал...")

    await page.goto(
        JOURNAL_URL,
        wait_until="domcontentloaded",
        timeout=60_000,
    )

    await page.wait_for_function(
        JOURNAL_READY,
        timeout=30_000,
    )


def _session_path(session_key: str) -> Path:
    return SESSIONS_DIR / f"{session_key}.bin"


def load_session(session_key: str | None) -> dict | None:
    """Сохранённые cookies Platonus. Хранятся зашифрованными."""
    if session_key is None:
        return None

    path = _session_path(session_key)

    try:
        return json.loads(get_cipher().decrypt(path.read_bytes()))
    except (FileNotFoundError, InvalidToken, ValueError):
        return None


def save_session(session_key: str | None, state: dict):
    if session_key is None:
        return

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    data = get_cipher().encrypt(json.dumps(state).encode("utf-8"))
    _session_path(session_key).write_bytes(data)


class BrowserHolder:
    """Один браузер на весь бот вместо запуска на каждую проверку."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None

    async def get(self):
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                if self._playwright is None:
                    self._playwright = await async_playwright().start()

                self._browser = await self._playwright.chromium.launch(
                    headless=not SHOW_BROWSER,
                    slow_mo=SLOW_MO,
                )

            return self._browser

    async def close(self):
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None

            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None


browser_holder = BrowserHolder()


def is_browser_gone(error: Exception) -> bool:
    """Браузер закрыт или упал — дело не в Platonus и не в пароле.

    Так бывает, например, при остановке бота: PyCharm закрывает
    и браузер, пока проверка ещё идёт.
    """
    text = str(error)
    return any(
        mark in text
        for mark in (
            "has been closed",
            "Connection closed",
            "Browser closed",
            "browser has disconnected",
        )
    )


async def save_debug_snapshot(page, session_key: str | None) -> Path | None:
    """Сохраняет скриншот и HTML страницы, на которой случилась ошибка."""
    # Пустая страница — ошибка случилась до загрузки, снимок ничего не покажет.
    if page.is_closed() or page.url == "about:blank":
        return None

    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = DEBUG_DIR / f"{stamp}_{session_key or 'manual'}"

        await page.screenshot(path=f"{base}.png", full_page=True)
        Path(f"{base}.html").write_text(await page.content(), encoding="utf-8")

        # Старые снимки удаляются, чтобы папка не разрасталась.
        files = sorted(
            (path for path in DEBUG_DIR.iterdir() if path.is_file()),
            key=lambda path: path.stat().st_mtime,
        )
        for old in files[:-DEBUG_KEEP_FILES]:
            old.unlink(missing_ok=True)

        return Path(f"{base}.png")
    except Exception:
        logger.warning("Не удалось сохранить снимок страницы", exc_info=True)
        return None


def print_grades(grades):
    subjects = {row["subject"] for row in grades}

    print(f"\nДисциплин: {len(subjects)}")
    print(f"Строк занятий: {len(grades)}")

    for row in grades:
        print(f"\n{row['subject']}")
        print(f"Поток: {row['stream']}")

        weekly_marks = [
            f"Неделя {week}: {value}"
            for week, value in row["marks"].items()
            if week.isdigit() and value is not None and str(value).strip()
        ]

        print(
            " | ".join(weekly_marks)
            if weekly_marks
            else "Оценок по неделям пока нет"
        )


async def fetch_grades(
    login: str,
    password: str,
    *,
    background: bool = False,
    session_key: str | None = None,
):
    """Загружает журнал. session_key — ключ сохранённой сессии,
    обычно Telegram ID: с ней повторный вход не нужен."""
    browser = await browser_holder.get()
    context = await browser.new_context(
        storage_state=load_session(session_key),
    )

    page = None

    try:
        page = await context.new_page()
        logger.info("Загружаю журнал пользователя %s", session_key or "из .env")

        if session_key is not None and await journal_is_open(page):
            logger.info("Сохранённая сессия действует, вход не нужен.")
        else:
            await open_journal(
                page,
                login,
                password,
                interactive=SHOW_BROWSER and not background,
            )

        grades = await page.evaluate(EXTRACT_GRADES)
        save_session(session_key, await context.storage_state())
        logger.info("Журнал загружен: %s строк.", len(grades))
        return grades
    except Exception as error:
        if page is not None:
            snapshot = await save_debug_snapshot(page, session_key)
            logger.warning(
                "Журнал не загружен (%s) на странице %s. Снимок: %s",
                type(error).__name__,
                page.url,
                snapshot,
            )
        raise
    finally:
        await context.close()


async def _open_schedule(page, language: str) -> dict | None:
    """Открывает страницу расписания и перехватывает её запрос данных.

    None — сессии нет (Platonus не отдал данные).
    """
    try:
        async with page.expect_response(
            lambda response: SCHEDULE_API in response.url,
            timeout=25_000,
        ) as info:
            await page.goto(SCHEDULE_URL, wait_until="domcontentloaded", timeout=60_000)

        response = await info.value
    except TimeoutError:
        return None

    if response.status != 200:
        return None

    # Страница запрашивает расписание на языке своего интерфейса.
    # Тот же запрос можно повторить на русском.
    if language == "ru" and response.url.endswith("/kz"):
        request = response.request
        repeated = await page.request.post(
            response.url[:-3] + "/ru",
            data=request.post_data,
            headers=request.headers,
        )

        if repeated.ok:
            return await repeated.json()

    return await response.json()


async def fetch_schedule(
    login: str,
    password: str,
    *,
    background: bool = False,
    session_key: str | None = None,
    language: str = "kk",
) -> dict:
    """Расписание текущей недели — исходный ответ Platonus."""
    browser = await browser_holder.get()
    context = await browser.new_context(
        storage_state=load_session(session_key),
    )
    page = None

    try:
        page = await context.new_page()
        logger.info("Загружаю расписание пользователя %s", session_key or "из .env")
        raw = await _open_schedule(page, language)

        if raw is None:
            # Сессия устарела — входим заново и пробуем ещё раз.
            await open_journal(
                page,
                login,
                password,
                interactive=SHOW_BROWSER and not background,
            )
            raw = await _open_schedule(page, language)

        if raw is None or "timetable" not in raw:
            raise ValueError("Platonus не отдал расписание.")

        save_session(session_key, await context.storage_state())
        return raw
    except Exception as error:
        if page is not None:
            snapshot = await save_debug_snapshot(page, session_key)
            logger.warning(
                "Расписание не загружено (%s) на странице %s. Снимок: %s",
                type(error).__name__,
                page.url,
                snapshot,
            )
        raise
    finally:
        await context.close()


async def main():
    try:
        grades = await fetch_grades(
            login=os.getenv("PLATONUS_LOGIN", "").strip(),
            password=os.getenv("PLATONUS_PASSWORD", ""),
        )
    finally:
        await browser_holder.close()

    print_grades(grades)


if __name__ == "__main__":
    from config import setup_logging

    setup_logging()
    asyncio.run(main())

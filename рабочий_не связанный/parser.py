import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError


ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "browser_profile"
OUTPUT_FILE = ROOT / "grades.json"

LOGIN_URL = "https://edu.enu.kz/"
JOURNAL_URL = (
    "https://edu.enu.kz/current_progress_gradebook_student?null"
)

load_dotenv(
    ROOT / ".env",
    encoding="utf-8-sig",
    interpolate=False,
)

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


async def open_journal(page):
    print("Проверяю сохранённый вход...")

    await page.goto(
        JOURNAL_URL,
        wait_until="domcontentloaded",
        timeout=60_000,
    )

    try:
        await page.wait_for_function(
            JOURNAL_READY,
            timeout=10_000,
        )
        print("Журнал доступен, повторный вход не нужен.")
        return

    except TimeoutError:
        pass

    login = os.getenv("PLATONUS_LOGIN", "").strip()
    password = os.getenv("PLATONUS_PASSWORD", "")

    if not login or not password:
        raise ValueError(
            "Укажи PLATONUS_LOGIN и PLATONUS_PASSWORD "
            "в файле .env рядом с parser.py."
        )

    print("Выполняю автоматический вход...")

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
        print(
            "\nВход пока не завершён. Посмотри открытый браузер.\n"
            "Если нужен код подтверждения или капча, "
            "введи их там самостоятельно.\n"
            "Если указана ошибка входа, проверь данные в .env.\n"
            "Скрипт подождёт ещё 2 минуты."
        )

        await page.wait_for_url(
            is_logged_in_url,
            wait_until="domcontentloaded",
            timeout=120_000,
        )

    print("Вход выполнен. Открываю журнал...")

    await page.goto(
        JOURNAL_URL,
        wait_until="domcontentloaded",
        timeout=60_000,
    )

    await page.wait_for_function(
        JOURNAL_READY,
        timeout=30_000,
    )


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
            if week.isdigit() and value and value != "н.п."
        ]

        print(
            " | ".join(weekly_marks)
            if weekly_marks
            else "Оценок по неделям пока нет"
        )


async def main():
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            # channel="chrome",
            headless=False,
        )

        try:
            page = (
                context.pages[0]
                if context.pages
                else await context.new_page()
            )

            await open_journal(page)

            grades = await page.evaluate(EXTRACT_GRADES)

            OUTPUT_FILE.write_text(
                json.dumps(
                    grades,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            print_grades(grades)
            print(f"\nОценки сохранены в: {OUTPUT_FILE}")

        except ValueError as error:
            print(f"\n{error}")

        except TimeoutError:
            print(
                "\nНе удалось завершить вход или загрузить журнал.\n"
                "Проверь данные в .env и доступность Platonus."
            )

        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())


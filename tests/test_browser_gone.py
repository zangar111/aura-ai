import asyncio

from playwright.async_api import Error as BrowserError

import grades_service
from parser import is_browser_gone


def test_is_browser_gone():
    assert is_browser_gone(BrowserError("Target page, context or browser has been closed"))
    assert is_browser_gone(BrowserError("Connection closed while reading from the driver"))
    assert not is_browser_gone(BrowserError("Timeout 20000ms exceeded."))
    assert not is_browser_gone(ValueError("Логин и пароль Platonus не переданы."))


def test_monitor_stops_when_browser_closed(monkeypatch):
    calls = []

    monkeypatch.setattr(grades_service, "get_connected_user_ids", lambda: [1, 2, 3])
    monkeypatch.setattr(grades_service, "get_user", lambda telegram_id: ("login", "pass"))

    async def closed_browser(login, password, **kwargs):
        calls.append(kwargs["session_key"])
        raise BrowserError("Target page, context or browser has been closed")

    monkeypatch.setattr(grades_service, "fetch_grades", closed_browser)

    async def run():
        stop = asyncio.Event()
        task = asyncio.create_task(
            grades_service.monitor_grades(bot=None, interval_seconds=3600, stop_event=stop)
        )
        await asyncio.sleep(0.5)
        stop.set()
        await task

    asyncio.run(run())

    # Первый же «браузер закрыт» прерывает круг: остальных не трогаем.
    assert calls == ["1"]
    assert not grades_service.grades_in_progress

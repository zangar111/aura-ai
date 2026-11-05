import asyncio

from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage

import blocked_users
import grades_service
from conftest import make_row


def forbidden():
    return TelegramForbiddenError(
        method=SendMessage(chat_id=1, text="x"),
        message="Forbidden: bot was blocked by the user",
    )


def test_mark_and_unmark():
    blocked_users.mark_blocked(10)
    assert blocked_users.is_blocked(10)
    assert 10 in blocked_users.blocked_ids()

    blocked_users.mark_active(10)
    assert not blocked_users.is_blocked(10)


def test_monitor_stops_checking_blocked_user(monkeypatch):
    fetch_calls = []
    stored = []

    monkeypatch.setattr(grades_service, "get_connected_user_ids", lambda: [77])
    monkeypatch.setattr(grades_service, "get_user", lambda telegram_id: ("login", "pass"))

    async def fake_fetch(login, password, **kwargs):
        fetch_calls.append(kwargs["session_key"])
        return [make_row(**{"1": "90"})]

    async def fake_store(bot, telegram_id, grades):
        stored.append(telegram_id)
        # Журнал сохранён, а сообщение не дошло: бот заблокирован.
        raise forbidden()

    async def no_schedule(telegram_id):
        pass

    monkeypatch.setattr(grades_service, "fetch_grades", fake_fetch)
    monkeypatch.setattr(grades_service, "store_grades", fake_store)
    monkeypatch.setattr(grades_service, "refresh_if_stale", no_schedule)

    async def run():
        stop = asyncio.Event()
        task = asyncio.create_task(
            grades_service.monitor_grades(bot=None, interval_seconds=0, stop_event=stop)
        )
        # Даём монитору пройти несколько кругов.
        await asyncio.sleep(2.5)
        stop.set()
        await task

    try:
        asyncio.run(run())

        # Первый круг загрузил журнал, дальше пользователь пропускается.
        assert fetch_calls == ["77"]
        assert stored == [77]
        assert blocked_users.is_blocked(77)
    finally:
        blocked_users.mark_active(77)

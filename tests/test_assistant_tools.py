import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import assistant_tools
from assistant_tools import ToolContext, ToolError, execute_tool, parse_remind_at

TZ = ZoneInfo("Asia/Almaty")
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=TZ)


def make_ctx(text="напомни", notes=None):
    async def nothing():
        return None

    return ToolContext(
        telegram_id=1,
        user_text=text,
        notes=notes if notes is not None else [],
        tz=TZ,
        now=NOW,
        show_grades=nothing,
        fetch_grades=nothing,
    )


def run(ctx, name, arguments):
    return asyncio.run(execute_tool(ctx, name, arguments))


def test_unknown_tool():
    assert "error" in run(make_ctx(), "drop_database", "{}")


@pytest.mark.parametrize(
    "arguments",
    [
        '{"note_id": "5"}',  # строка вместо числа
        '{"note_id": 0}',
        '{"note_id": 5, "extra": 1}',
        "не json",
    ],
)
def test_bad_arguments_are_rejected(arguments):
    assert "error" in run(make_ctx(), "delete_note", arguments)


def test_cannot_delete_foreign_note():
    result = run(make_ctx(notes=[]), "delete_note", '{"note_id": 7}')
    assert result == {"error": "У пользователя нет заметки с таким id."}


def test_url_must_come_from_user():
    result = run(make_ctx("сохрани"), "save_note", '{"topic": "x", "url": "https://evil.example"}')
    assert "error" in result


def test_save_note_with_reminder(monkeypatch):
    saved = {}

    def fake_save(**kwargs):
        saved.update(kwargs)
        return 42

    monkeypatch.setattr(assistant_tools.database, "create_profile", lambda telegram_id: None)
    monkeypatch.setattr(assistant_tools.database, "save_note", fake_save)

    ctx = make_ctx("напомни завтра в 9 про лабу")
    result = run(ctx, "save_note", '{"topic": "Лаба", "remind_at": "2026-10-23T09:00"}')

    assert result == {"ok": True, "note_id": 42, "remind_at": "2026-10-23T09:00"}
    assert saved["remind_at"] == datetime(2026, 10, 23, 9, 0, tzinfo=TZ)
    assert ctx.actions == ["Сохранил заметку: Лаба."]


def test_get_grades_without_platonus():
    result = run(make_ctx(), "get_grades", '{"refresh": true}')
    assert "/connect" in result["error"]


def test_parse_remind_at():
    assert parse_remind_at(None, TZ, NOW) is None
    assert parse_remind_at("2026-10-22T18:30", TZ, NOW).hour == 18

    with pytest.raises(ToolError):
        parse_remind_at("завтра", TZ, NOW)

    with pytest.raises(ToolError):
        parse_remind_at((NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"), TZ, NOW)

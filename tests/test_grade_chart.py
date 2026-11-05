import asyncio

import pytest

import assistant_tools
from conftest import make_row
from grade_chart import find_subject, render_progress_chart, weekly_series
from grades_service import UnknownSubject
from test_assistant_tools import make_ctx

GRADES = [
    make_row(stream="BT 1-2-L", **{"1": "н.п.", "2": "90", "3": "", "ТК1": "80"}),
    make_row(stream="BT 1-2-Lab", **{"1": "80", "2": "85,5"}),
    make_row(subject="Глубокое обучение", stream="DL 1-Lab", **{"1": "70"}),
]

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_weekly_series_parses_marks():
    series = weekly_series(GRADES)

    assert series["Блокчейн технологии"]["L"] == {1: "absent", 2: 90.0}
    assert series["Блокчейн технологии"]["Lab"] == {1: 80.0, 2: 85.5}
    assert set(series) == {"Блокчейн технологии", "Глубокое обучение"}


def test_find_subject_with_typos():
    subjects = list(weekly_series(GRADES))
    assert find_subject(subjects, "блокчеин") == "Блокчейн технологии"
    assert find_subject(subjects, "глубокого обучения") == "Глубокое обучение"
    assert find_subject(subjects, "футбол") is None


@pytest.mark.parametrize("language", ["kk", "ru"])
def test_renders_png(language):
    assert render_progress_chart(GRADES, language).startswith(PNG_SIGNATURE)
    one = render_progress_chart(GRADES, language, subject="Блокчейн технологии")
    assert one.startswith(PNG_SIGNATURE)


def test_empty_journal_is_rejected():
    with pytest.raises(ValueError):
        render_progress_chart([make_row(**{"ТК1": "80"})])


def test_chart_tool_reports_unknown_subject():
    async def fail(subject):
        raise UnknownSubject(["Блокчейн технологии"])

    ctx = make_ctx()
    ctx.show_chart = fail
    result = asyncio.run(
        assistant_tools.execute_tool(ctx, "show_grade_chart", '{"subject": "футбол"}')
    )
    assert "Блокчейн технологии" in result["error"]


def test_chart_tool_marks_reply_as_sent():
    async def ok(subject):
        return subject

    ctx = make_ctx()
    ctx.show_chart = ok
    result = asyncio.run(
        assistant_tools.execute_tool(ctx, "show_grade_chart", '{"subject": "Блокчейн технологии"}')
    )
    assert result["ok"] and ctx.reply_optional

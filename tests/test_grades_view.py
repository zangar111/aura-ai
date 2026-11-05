from conftest import make_row
from grade_summary import compact_grades
from grades_service import format_grades


def test_compact_drops_empty_and_splits_weeks():
    rows = [make_row(**{"1": "90", "2": "", "ТК1": "80.0", "РК1": None})]

    [result] = compact_grades(rows)

    assert result["subject"] == "Блокчейн технологии"
    assert result["type"] == "L"
    assert result["weeks"] == {"1": "90"}
    assert result["totals"] == {"ТК1": "80.0"}


def test_format_marks_recent_change():
    rows = [make_row(**{"1": "90", "2": "75"})]
    changes = [
        {
            "subject": "Блокчейн технологии",
            "stream": "BT 1-2-L",
            "column": "2",
            "new_value": "75",
            "kind": "updated",
        }
    ]

    html = format_grades(rows, changes)

    assert "<mark><b>75</b></mark> 🔄" in html
    assert "<mark><b>90</b></mark>" not in html


def test_format_escapes_html():
    rows = [make_row(subject="<script>", **{"1": "<b>"})]
    html = format_grades(rows)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_format_splits_long_tables():
    rows = [make_row(**{str(week): "1" for week in range(1, 25)})]
    html = format_grades(rows)
    assert "часть 1" in html and "часть 2" in html

import pytest

from conftest import make_row
from grade_changes import (
    JournalStructureChanged,
    compare_grades,
    journal_structure,
)


def marks(**values):
    # Столбцы-недели в журнале — строки "1", "2", ...
    return {key.lstrip("w"): value for key, value in values.items()}


def test_first_journal_has_no_changes():
    assert compare_grades(None, [make_row(**marks(w1="90"))]) == []


def test_detects_new_updated_removed():
    old = [make_row(**marks(w1="", w2="80", w3="70"))]
    new = [make_row(**marks(w1="95", w2="85", w3=""))]

    changes = {c["column"]: c["kind"] for c in compare_grades(old, new)}

    assert changes == {"1": "new", "2": "updated", "3": "removed"}


def test_unchanged_journal_gives_nothing():
    rows = [make_row(**marks(w1="90"))]
    assert compare_grades(rows, rows) == []


def test_whitespace_and_trailing_underscore_are_ignored():
    old = [make_row(subject="Блокчейн_", stream="BT  1", **marks(w1="90"))]
    new = [make_row(subject="Блокчейн", stream="BT 1", **marks(w1=" 90 "))]
    assert compare_grades(old, new) == []


def test_new_column_is_a_change_not_an_error():
    old = [make_row(**marks(w1="90"))]
    new = [make_row(**marks(w1="90", w2="100"))]
    assert [c["kind"] for c in compare_grades(old, new)] == ["new"]


def test_missing_cells_raise_structure_changed():
    old = [make_row(**marks(w1="90", w2="80"))]
    new = [make_row(subject="Другой предмет", **marks(w1="90"))]

    with pytest.raises(JournalStructureChanged) as error:
        compare_grades(old, new)

    assert len(error.value.missing) == 2
    # Старый код ловил ValueError — он должен продолжать работать.
    assert isinstance(error.value, ValueError)


def test_structure_ignores_values():
    a = [make_row(**marks(w1="90"))]
    b = [make_row(**marks(w1="10"))]
    assert journal_structure(a) == journal_structure(b)


@pytest.mark.parametrize(
    "grades",
    [
        [],
        [{"subject": "A", "stream": "s", "marks": {}}],
        [{"subject": "", "stream": "s", "marks": {"1": "5"}}],
        [make_row(**marks(w1="1")), make_row(**marks(w1="2"))],
    ],
)
def test_invalid_journal_is_rejected(grades):
    with pytest.raises(ValueError):
        compare_grades(None, grades)

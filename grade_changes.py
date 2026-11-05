# Столбцы, которые выставляет преподаватель. Остальные (ТК, ТК ОБЩ., Р1,
# Р2, рейтинг допуска, итог в %) Platonus пересчитывает сам после каждой
# новой оценки — уведомлять о них незачем.
IMPORTANT_COLUMNS = {
    "РК1",
    "РК2",
    "Итоговый контроль",
    "Итоговая оценка (Буквенная)",
    "Оценка за курсовую работу",
    "Практика",
    "Исследоват. работа",
}


def is_important(column: str) -> bool:
    """Оценка за неделю или столбец, который ставит преподаватель."""
    column = " ".join(column.split())
    return column.isdigit() or column in IMPORTANT_COLUMNS


class JournalStructureChanged(ValueError):
    """В новом журнале исчезли строки или столбцы прежнего."""

    def __init__(self, missing: set):
        super().__init__(
            "В новом журнале исчезли строки или столбцы. "
            "Нужно проверить полноту загрузки и структуру журнала."
        )
        self.missing = missing


def journal_structure(grades: list[dict]) -> frozenset:
    """Набор ячеек журнала без значений — «форма» журнала."""
    return frozenset(_index_grades(grades))


def _index_grades(grades: list[dict]) -> dict:
    if not isinstance(grades, list) or not grades:
        raise ValueError("Журнал должен быть непустым списком.")

    cells = {}

    for row in grades:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("subject"), str)
            or not isinstance(row.get("stream"), str)
            or not isinstance(row.get("marks"), dict)
            or not row["marks"]
        ):
            raise ValueError("Неверная структура строки журнала.")

        subject = " ".join(row["subject"].split()).rstrip("_").strip()
        stream = " ".join(row["stream"].split())

        if not subject or not stream:
            raise ValueError("Не указан предмет или поток.")

        for column, value in row["marks"].items():
            if not isinstance(column, str) or not column.strip():
                raise ValueError("У столбца нет названия.")

            column = " ".join(column.split())
            key = (subject, stream, column)

            if key in cells:
                raise ValueError(
                    "В журнале повторяется одна и та же ячейка."
                )

            cells[key] = "" if value is None else str(value).strip()

    return cells


def compare_grades(
    old_grades: list[dict] | None,
    new_grades: list[dict],
) -> list[dict]:
    new_cells = _index_grades(new_grades)

    # Первый журнал становится исходным снимком.
    if old_grades is None:
        return []

    old_cells = _index_grades(old_grades)

    missing = old_cells.keys() - new_cells.keys()

    if missing:
        raise JournalStructureChanged(missing)

    changes = []

    for key, new_value in new_cells.items():
        old_value = old_cells.get(key, "")

        if old_value == new_value:
            continue

        if not old_value:
            kind = "new"
        elif not new_value:
            kind = "removed"
        else:
            kind = "updated"

        subject, stream, column = key

        changes.append({
            "subject": subject,
            "stream": stream,
            "column": column,
            "old_value": old_value,
            "new_value": new_value,
            "kind": kind,
        })

    return changes


if __name__ == "__main__":
    old = [{
        "subject": "Пример",
        "stream": "TEST-1-Lab",
        "marks": {"5": "80", "6": ""},
    }]

    new = [{
        "subject": "Пример",
        "stream": "TEST-1-Lab",
        "marks": {"5": "95", "6": "0"},
    }]

    for change in compare_grades(old, new):
        print(
            change["column"],
            change["old_value"] or "пусто",
            "->",
            change["new_value"] or "пусто",
            change["kind"],
        )
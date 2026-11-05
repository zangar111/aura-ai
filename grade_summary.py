def compact_grades(grades: list[dict]) -> list[dict]:
    """Короткий вид журнала для ИИ: без пустых ячеек.

    Недели и итоговые столбцы разделены, чтобы ИИ
    не путал номер недели с баллом.
    """
    result = []

    for row in grades:
        weeks = {}
        totals = {}

        for column, value in row["marks"].items():
            text = "" if value is None else str(value).strip()

            if not text:
                continue

            if column.isdigit():
                weeks[column] = text
            else:
                totals[column] = text

        stream = row["stream"].strip()

        result.append(
            {
                "subject": " ".join(row["subject"].split()).rstrip("_").strip(),
                "type": stream.rsplit("-", 1)[-1].strip() or stream,
                "stream": stream,
                "weeks": weeks,
                "totals": totals,
            }
        )

    return result

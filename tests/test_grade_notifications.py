import asyncio

import grades_service
from grade_changes import is_important


def change(id, column, new, old="", kind="new", stream="OD 192252-1-L", subject="Обработка данных"):
    return {
        "id": id, "subject": subject, "stream": stream, "column": column,
        "old_value": old, "new_value": new, "kind": kind,
    }


# Пример из реального уведомления, которое было «нечитаемым».
REAL_EXAMPLE = [
    change(1, "8", "50"),
    change(2, "ТК2", "6.25", old="0.0", kind="updated"),
    change(3, "ТК2 ОБЩ.", "4.38", old="3.13", kind="updated"),
    change(4, "ТК2 ОБЩ.", "4.38", old="3.13", kind="updated", stream="OD 192252-1-SRO"),
    change(5, "ТК2 ОБЩ.", "4.38", old="3.13", kind="updated", stream="OD 192252-7-Lab"),
]


def test_important_columns():
    for column in ["1", "15", "РК1", "РК2", "Итоговый контроль", "Итоговая оценка (Буквенная)"]:
        assert is_important(column), column

    for column in ["ТК1", "ТК1 ОБЩ.", "ТК2", "ТК2 ОБЩ.", "Р1", "Р2", "Рейтинг допуска", "Итоговая оценка (%)"]:
        assert not is_important(column), column


def run_notify(monkeypatch, pending, language="kk"):
    marked = []
    sent_messages = []

    monkeypatch.setattr(grades_service, "get_pending_grade_changes", lambda telegram_id: pending)
    monkeypatch.setattr(
        grades_service, "mark_grade_changes_notified",
        lambda telegram_id, ids: marked.append(sorted(ids)),
    )

    async def language_of(telegram_id):
        return language

    monkeypatch.setattr(grades_service, "user_language", language_of)

    class FakeBot:
        async def send_message(self, chat_id, text, parse_mode=None, disable_notification=False):
            sent_messages.append((text, parse_mode))

    result = asyncio.run(grades_service.notify_grade_changes(FakeBot(), 1))
    return result, marked, sent_messages


def test_real_example_becomes_one_short_line(monkeypatch):
    result, marked, messages = run_notify(monkeypatch, REAL_EXAMPLE)

    assert [item["id"] for item in result] == [1]
    # Пересчёты отмечены без уведомления, оценка — после отправки.
    assert marked == [[2, 3, 4, 5], [1]]
    assert messages == [(
        "🔔 <b>Жаңа бағалар</b>\n\n"
        "📘 <b>Обработка данных</b>\n"
        "Дәріс · 8-апта — <b>50</b>\n\n"
        "Толық журнал: /grades",
        "HTML",
    )]


def test_only_recalculated_columns_send_nothing(monkeypatch):
    result, marked, messages = run_notify(monkeypatch, REAL_EXAMPLE[1:])
    assert result == [] and messages == []
    assert marked == [[2, 3, 4, 5]]


def test_grouping_and_russian(monkeypatch):
    pending = [
        change(1, "РК1", "85"),
        change(2, "7", "90", old="70", kind="updated", stream="OD 192252-7-Lab"),
        change(3, "8", "50"),
        change(4, "8", "", old="40", kind="removed", subject="Блокчейн технологии_", stream="BT 1-2-L"),
        change(5, "Итоговый контроль", "92", subject="Блокчейн технологии_", stream="BT 1-2-L"),
    ]
    _, _, messages = run_notify(monkeypatch, pending, language="ru")

    assert messages[0][0] == (
        "🔔 <b>Изменения в оценках</b>\n\n"
        "📘 <b>Обработка данных</b>\n"
        "Лекция · 8-я неделя — <b>50</b>\n"
        "Лекция · РК1 — <b>85</b>\n"
        "Лабораторная · 7-я неделя — <s>70</s> → <b>90</b>\n\n"
        "📘 <b>Блокчейн технологии</b>\n"
        "Лекция · 8-я неделя — <s>40</s> удалена\n"
        "Лекция · Экзамен — <b>92</b>\n\n"
        "Полный журнал: /grades"
    )


def test_long_list_is_split_between_messages(monkeypatch):
    # 180 предметов не влезут в одно сообщение — остаток придёт позже.
    pending = [
        change(number, str(number % 15 + 1), "90", subject=f"Предмет с длинным названием {number}")
        for number in range(1, 181)
    ]
    result, _, messages = run_notify(monkeypatch, pending)

    assert 0 < len(result) < len(pending)
    assert len(messages[0][0]) <= grades_service.NOTIFICATION_LIMIT

import asyncio

import pytest

import grades_service
from conftest import make_row

GRADES = [make_row(**{"1": "90"})]
CHANGE = {"id": 1, "subject": "Блокчейн технологии", "stream": "BT 1-2-L",
          "column": "1", "old_value": "", "new_value": "90", "kind": "new"}


@pytest.fixture
def summaries(monkeypatch):
    sent = []

    monkeypatch.setattr(grades_service, "save_grade_snapshot", lambda *args, **kwargs: [])

    async def fake_summary(bot, telegram_id, grades, changes=None):
        sent.append((telegram_id, changes))

    monkeypatch.setattr(grades_service, "send_grade_summary", fake_summary)
    return sent


def use_notifications(monkeypatch, changes):
    async def fake_notify(bot, telegram_id):
        return changes

    monkeypatch.setattr(grades_service, "notify_grade_changes", fake_notify)


def test_summary_after_notification(monkeypatch, summaries):
    use_notifications(monkeypatch, [CHANGE])
    asyncio.run(grades_service.store_grades(None, 5, GRADES))
    assert summaries == [(5, [CHANGE])]


def test_no_summary_without_changes(monkeypatch, summaries):
    use_notifications(monkeypatch, [])
    asyncio.run(grades_service.store_grades(None, 5, GRADES))
    assert summaries == []


def test_summary_can_be_disabled(monkeypatch, summaries):
    use_notifications(monkeypatch, [CHANGE])
    asyncio.run(grades_service.store_grades(None, 5, GRADES, with_summary=False))
    assert summaries == []


def test_summary_uses_default_language(monkeypatch):
    languages = []
    messages = []

    monkeypatch.setattr(grades_service, "get_language", lambda telegram_id: None)

    async def fake_summarize(grades, changes, language):
        languages.append(language)
        return {"changes": [], "overall": "Бәрі жақсы", "risks": [], "tip": ""}

    buttons = []

    class FakeBot:
        async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
            messages.append((text, parse_mode))
            buttons.extend(
                (button.text, button.callback_data)
                for row in reply_markup.inline_keyboard
                for button in row
            )

    monkeypatch.setattr(grades_service, "summarize_grades", fake_summarize)
    asyncio.run(grades_service.send_grade_summary(FakeBot(), 5, GRADES))

    assert languages == ["kk"]
    # Под сводкой — кнопка графика на языке пользователя.
    assert buttons == [("📈 Прогресс графигі", "chart")]
    assert messages == [
        (
            "📊 <b>Бағалар бойынша қысқаша шолу</b>\n\n"
            "✅ <b>Жалпы жағдай</b>\nБәрі жақсы",
            "HTML",
        )
    ]


def test_render_full_summary_in_russian():
    text = grades_service.render_grade_summary(
        {
            "changes": ["Блокчейн технологии (лекция): 7-я неделя — 90"],
            "overall": "В основном 80–100",
            "risks": ["Обработка данных (СРО) — 50 <низко>", "Мобильные (СРО) — 5 н.п."],
            "tip": "Закрой пропуски",
        },
        "ru",
    )

    assert text == (
        "📊 <b>Краткая сводка по оценкам</b>\n\n"
        "🆕 <b>Новые оценки</b>\n• Блокчейн технологии (лекция): 7-я неделя — 90\n\n"
        "✅ <b>В целом</b>\nВ основном 80–100\n\n"
        "⚠️ <b>Обратить внимание</b>\n"
        "• Обработка данных (СРО) — 50 &lt;низко&gt;\n• Мобильные (СРО) — 5 н.п.\n\n"
        "💡 <b>Совет:</b> Закрой пропуски"
    )

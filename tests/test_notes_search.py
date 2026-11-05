from notes_search import search_notes, select_relevant_notes


def note(note_id, topic, text="", url=None):
    return {"id": note_id, "topic": topic, "original_text": text, "url": url}


NOTES = [
    note(3, "Лабораторная по базам данных", "сдать до пятницы"),
    note(2, "Блокчейн технологии", "лекция", "https://example.com/bc"),
    note(1, "Интеллектуалды жүйелер", "презентация"),
]


def test_finds_by_word_ending():
    assert [n["id"] for n in search_notes(NOTES, "блокчейну")] == [2]


def test_finds_with_typo():
    assert [n["id"] for n in search_notes(NOTES, "блокчеин")] == [2]


def test_finds_kazakh_word_by_prefix():
    assert [n["id"] for n in search_notes(NOTES, "интеллектуалдық")] == [1]


def test_short_words_do_not_match_everything():
    assert search_notes(NOTES, "по") == []


def test_unrelated_query_finds_nothing():
    assert search_notes(NOTES, "футбол") == []


def test_few_notes_are_all_selected():
    assert select_relevant_notes(NOTES, "что угодно") == NOTES


def test_many_notes_keep_recent_and_relevant():
    many = [note(i, f"Заметка {i}") for i in range(100, 40, -1)]
    old_match = note(1, "Блокчейн технологии")
    notes = many + [old_match]

    selected = select_relevant_notes(notes, "дай ссылку про блокчейн", limit=30, recent=10)

    assert old_match in selected
    assert selected[:10] == many[:10]
    assert len(selected) <= 30

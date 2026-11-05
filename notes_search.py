import re
from difflib import SequenceMatcher

WORD = re.compile(r"\w+", re.UNICODE)


def _words(text: str) -> list[str]:
    return [word for word in WORD.findall(text.lower()) if len(word) >= 3]


def _word_score(query_word: str, note_words: list[str]) -> float:
    best = 0.0

    for word in note_words:
        # Общее начало слова прощает окончания: «блокчейну» ~ «блокчейн».
        if (
            len(word) >= 5
            and len(query_word) >= 5
            and word[:5] == query_word[:5]
        ):
            return 1.0

        best = max(best, SequenceMatcher(None, query_word, word).ratio())

    return best if best >= 0.75 else 0.0


def note_score(note: dict, query: str) -> float:
    query_words = _words(query)

    if not query_words:
        return 0.0

    note_words = _words(
        " ".join(
            str(note.get(field) or "")
            for field in ("topic", "original_text", "url")
        )
    )

    if not note_words:
        return 0.0

    return sum(_word_score(word, note_words) for word in query_words) / len(
        query_words
    )


def search_notes(notes: list[dict], query: str, limit: int = 5) -> list[dict]:
    """Нечёткий поиск: учитывает опечатки и разные окончания."""
    scored = [(note_score(note, query), note) for note in notes]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [note for _, note in scored[:limit]]


def select_relevant_notes(
    notes: list[dict],
    text: str,
    limit: int = 30,
    recent: int = 10,
) -> list[dict]:
    """Выбирает заметки, которые стоит передать ИИ.

    Если заметок немного, передаются все. Иначе — похожие на
    сообщение и несколько последних (на них часто ссылаются:
    «удали последнюю заметку»). Порядок исходного списка сохраняется.
    """
    if len(notes) <= limit:
        return notes

    chosen = {id(note) for note in notes[:recent]}

    for note in search_notes(notes, text, limit=limit):
        if len(chosen) >= limit:
            break
        chosen.add(id(note))

    return [note for note in notes if id(note) in chosen]

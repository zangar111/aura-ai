"""Оформление текста ИИ для Telegram.

ИИ привык писать Markdown (**жирный**, списки через «-»), а Telegram
его сам не понимает — звёздочки остаются в тексте. Здесь Markdown
переводится в HTML, который Telegram показывает как форматирование.
"""

import re
from html import escape

# Запас до лимита Telegram в 4096 символов: теги тоже считаются.
MESSAGE_LIMIT = 3500


def markdown_to_html(text: str) -> str:
    lines = []

    for line in text.split("\n"):
        # Разделители «---» в Telegram выглядят как мусор.
        if re.fullmatch(r"\s*([-*_])\1{2,}\s*", line):
            line = ""

        # Заголовки «## Текст» → жирная строка.
        heading = re.match(r"^\s*#{1,6}\s+(.*)$", line)
        if heading:
            line = f"**{heading.group(1).strip('* ')}**"

        # Пункты списка «- текст» → «• текст».
        bullet = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if bullet:
            line = f"{bullet.group(1)}• {bullet.group(2)}"

        lines.append(line)

    html = escape("\n".join(lines), quote=False)

    # Порядок важен: сначала код, чтобы не трогать звёздочки внутри него.
    html = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", r"<b>\1</b>", html)
    html = re.sub(r"__(?!\s)(.+?)(?<!\s)__", r"<b>\1</b>", html)
    html = re.sub(
        r"(?<![\w*])\*(?![\s*])([^*\n]+?)(?<!\s)\*(?![\w*])",
        r"<i>\1</i>",
        html,
    )
    html = re.sub(
        r"(?<![\w_])_(?![\s_])([^_\n]+?)(?<!\s)_(?![\w_])",
        r"<i>\1</i>",
        html,
    )
    html = re.sub(
        r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)",
        r'<a href="\2">\1</a>',
        html,
    )

    # Больше одной пустой строки подряд не нужно.
    return re.sub(r"\n{3,}", "\n\n", html).strip()


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Делит длинный текст по абзацам, не разрывая строки."""
    chunks = []
    current = ""

    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)

        # Слишком длинный абзац режется по строкам, а строка — по символам.
        while len(paragraph) > limit:
            cut = paragraph.rfind("\n", 0, limit)
            cut = cut if cut > 0 else limit
            chunks.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip("\n")

        current = paragraph

    if current:
        chunks.append(current)

    return chunks


def strip_markdown(text: str) -> str:
    """Запасной вариант: убрать разметку, если HTML не принят."""
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
    return re.sub(r"^(\s*)[-*+]\s+", r"\1• ", text, flags=re.M)

"""График прогресса: баллы по неделям для каждого предмета.

Рисуется картинкой (PNG) для отправки в Telegram. Цвета и толщины
линий подобраны по правилам читаемых графиков: у каждого типа занятия
свой цвет и своя форма маркера, чтобы их различали и люди с особенностями
цветового зрения.
"""

import io
import math
import textwrap

import matplotlib

matplotlib.use("Agg")  # без окна — рисуем сразу в файл

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from notes_search import note_score  # noqa: E402

# Цвет и маркер закреплены за типом занятия, а не за порядком.
SERIES = {
    "L": ("#2a78d6", "o"),
    "Lab": ("#eb6834", "s"),
    "SRO": ("#1baf7a", "^"),
}
OTHER_SERIES = ("#898781", "D")

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
ABSENT = "#d03b3b"  # «н.п.» — статус, а не серия

LABELS = {
    "kk": {
        "title": "Апталар бойынша баллдар",
        "week": "Апта",
        "absent": "н.п. — сабаққа қатыспады",
        "types": {"L": "Дәріс", "Lab": "Зертхана", "SRO": "СӨЖ"},
        "average": "орташа",
    },
    "ru": {
        "title": "Баллы по неделям",
        "week": "Неделя",
        "absent": "н.п. — пропуск",
        "types": {"L": "Лекция", "Lab": "Лабораторная", "SRO": "СРО"},
        "average": "среднее",
    },
}

ABSENT_MARKS = {"н.п.", "н/п", "нп", "н"}


def _subject_name(row: dict) -> str:
    return " ".join(row["subject"].split()).rstrip("_").strip()


def _lesson_type(row: dict) -> str:
    stream = row["stream"].strip()
    return stream.rsplit("-", 1)[-1].strip() or stream


def _parse_mark(value) -> float | str | None:
    """Число, «absent» для пропуска или None для пустой ячейки."""
    text = "" if value is None else str(value).strip().lower()

    if not text:
        return None

    if text in ABSENT_MARKS:
        return "absent"

    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def weekly_series(grades: list[dict]) -> dict[str, dict[str, dict[int, float | str]]]:
    """{предмет: {тип занятия: {неделя: балл или "absent"}}}."""
    result: dict = {}

    for row in grades:
        marks = {}

        for column, value in row["marks"].items():
            if not column.strip().isdigit():
                continue

            mark = _parse_mark(value)

            if mark is not None:
                marks[int(column)] = mark

        result.setdefault(_subject_name(row), {})[_lesson_type(row)] = marks

    return result


def find_subject(subjects: list[str], query: str) -> str | None:
    """Предмет по названию с опечатками или сокращением."""
    scored = [
        (note_score({"topic": subject}, query), subject) for subject in subjects
    ]
    best_score, best = max(scored, default=(0.0, None))
    return best if best_score >= 0.5 else None


def _style_axes(ax, last_week: int, show_xlabel: str | None):
    ax.set_facecolor(SURFACE)
    ax.set_ylim(-8, 108)
    ax.set_xlim(0.5, last_week + 0.5)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticks(range(1, last_week + 1, 2 if last_week > 10 else 1))
    ax.tick_params(colors=INK_MUTED, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)

    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)

    ax.spines["bottom"].set_color(BASELINE)

    # Порог допуска к экзамену — обычно 50.
    ax.axhline(50, color=BASELINE, linewidth=1, zorder=1)

    if show_xlabel:
        ax.set_xlabel(show_xlabel, color=INK_MUTED, fontsize=8)


def _draw_subject(ax, by_type: dict, labels: dict, direct_labels: bool):
    for lesson_type, marks in by_type.items():
        color, marker = SERIES.get(lesson_type, OTHER_SERIES)
        weeks = sorted(marks)

        if not weeks:
            continue

        # Пропуск разрывает линию: балла за эту неделю нет.
        xs = list(range(weeks[0], weeks[-1] + 1))
        ys = [
            marks[week] if isinstance(marks.get(week), float) else math.nan
            for week in xs
        ]

        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=2,
            marker=marker,
            markersize=6,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=3,
        )

        absent = [week for week in weeks if marks[week] == "absent"]

        if absent:
            ax.scatter(
                absent,
                [-3] * len(absent),
                marker="x",
                color=ABSENT,
                s=36,
                linewidths=2,
                zorder=4,
            )

    if direct_labels:
        _draw_end_labels(ax, by_type, labels)


def _draw_end_labels(ax, by_type: dict, labels: dict):
    """Подпись последнего балла у конца линии.

    Если концы линий слишком близко, их подписи наложились бы —
    такие линии подписывает только легенда.
    """
    ends = []

    for lesson_type, marks in by_type.items():
        numeric = [(week, value) for week, value in sorted(marks.items()) if isinstance(value, float)]

        if numeric:
            ends.append((lesson_type, *numeric[-1]))

    for lesson_type, week, value in ends:
        crowded = any(
            other != lesson_type and abs(other_value - value) < 9 and abs(other_week - week) < 3
            for other, other_week, other_value in ends
        )

        if crowded:
            continue

        name = labels["types"].get(lesson_type, lesson_type)
        ax.annotate(
            f"{name} {value:g}",
            (week, value),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=10,
            color=INK_SECONDARY,
        )


def _legend_handles(types: list[str], labels: dict, with_absent: bool):
    handles = []

    for lesson_type in types:
        color, marker = SERIES.get(lesson_type, OTHER_SERIES)
        handles.append(
            Line2D(
                [], [],
                color=color,
                linewidth=2,
                marker=marker,
                markersize=6,
                markeredgecolor=SURFACE,
                label=labels["types"].get(lesson_type, lesson_type),
            )
        )

    if with_absent:
        handles.append(
            Line2D(
                [], [],
                color=ABSENT,
                linestyle="none",
                marker="x",
                markersize=7,
                markeredgewidth=2,
                label=labels["absent"],
            )
        )

    return handles


def render_progress_chart(
    grades: list[dict],
    language: str = "kk",
    subject: str | None = None,
    subtitle: str | None = None,
) -> bytes:
    """PNG с графиком. subject — один предмет крупно, иначе все предметы."""
    labels = LABELS.get(language, LABELS["kk"])
    series = weekly_series(grades)

    if subject is not None:
        series = {subject: series[subject]}

    series = {name: types for name, types in series.items() if any(types.values())}

    if not series:
        raise ValueError("В журнале нет недельных оценок для графика.")

    last_week = max(
        [week for types in series.values() for marks in types.values() for week in marks]
        + [15]
    )
    types_present = [
        lesson_type
        for lesson_type in [*SERIES, *sorted({t for types in series.values() for t in types})]
        if any(lesson_type in types for types in series.values())
    ]
    types_present = list(dict.fromkeys(types_present))
    has_absent = any(
        mark == "absent"
        for types in series.values()
        for marks in types.values()
        for mark in marks.values()
    )

    plt.rcParams["font.family"] = "DejaVu Sans"
    single = len(series) == 1

    # Картинку смотрят на телефоне: одна колонка, крупный текст.
    header_inches = 1.25
    panel_inches = 3.6 if single else 2.25
    width = 7 if single else 6.4
    height = header_inches + panel_inches * len(series)

    fig, grid = plt.subplots(
        len(series), 1,
        figsize=(width, height),
        dpi=150,
        sharex=True,
        squeeze=False,
    )
    axes = list(grid.flat)
    fig.patch.set_facecolor(SURFACE)

    for index, (name, by_type) in enumerate(series.items()):
        ax = axes[index]
        is_bottom = index == len(series) - 1
        _style_axes(ax, last_week, labels["week"] if is_bottom else None)
        ax.tick_params(labelbottom=True)
        _draw_subject(ax, by_type, labels, direct_labels=single)

        numbers = [
            value
            for marks in by_type.values()
            for value in marks.values()
            if isinstance(value, float)
        ]
        average = f"  ·  {labels['average']} {sum(numbers) / len(numbers):.0f}" if numbers else ""

        ax.set_title(
            "\n".join(textwrap.wrap(name + average, 46)),
            loc="left",
            fontsize=12 if single else 10.5,
            color=INK,
            fontweight="bold",
            pad=6,
        )
        ax.tick_params(labelsize=9)

        if single:
            # Место справа под подписи на концах линий.
            ax.set_xlim(0.5, last_week + 3.5)

    # Шапка: заголовок, дата, легенда — в дюймах от верхнего края.
    def from_top(inches: float) -> float:
        return 1 - inches / height

    fig.text(0.03, from_top(0.38), labels["title"], fontsize=15, color=INK, fontweight="bold")

    if subtitle:
        fig.text(0.03, from_top(0.62), subtitle, fontsize=9.5, color=INK_MUTED)

    fig.legend(
        handles=_legend_handles(types_present, labels, has_absent),
        loc="upper left",
        ncol=len(types_present) + int(has_absent) if single else 2,
        frameon=False,
        fontsize=9.5,
        labelcolor=INK_SECONDARY,
        bbox_to_anchor=(0.015, from_top(0.68)),
        handlelength=2.2,
        columnspacing=1.2,
    )

    legend_rows = 1 if single else math.ceil((len(types_present) + int(has_absent)) / 2)
    header = 0.8 + 0.27 * legend_rows
    fig.tight_layout(rect=(0, 0, 1, from_top(header)), h_pad=1.6)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor=SURFACE)
    plt.close(fig)
    return buffer.getvalue()

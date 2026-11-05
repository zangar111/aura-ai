from formatting import markdown_to_html, split_message, strip_markdown


def test_bold_and_bullets_from_screenshot():
    text = (
        "**Ең нашар пәнің — «Проектирование интеллект. систем»** 📉\n\n"
        "- P1 = **71.5** (бүкіл журналда ең төмен)\n"
        "- Апта сайын 70–77"
    )

    assert markdown_to_html(text) == (
        "<b>Ең нашар пәнің — «Проектирование интеллект. систем»</b> 📉\n\n"
        "• P1 = <b>71.5</b> (бүкіл журналда ең төмен)\n"
        "• Апта сайын 70–77"
    )


def test_html_is_escaped():
    assert markdown_to_html("1 < 2 & **3 > 2**") == "1 &lt; 2 &amp; <b>3 &gt; 2</b>"


def test_headings_and_rules():
    assert markdown_to_html("## Итог\n---\nтекст") == "<b>Итог</b>\n\nтекст"


def test_links_and_urls_with_underscores_stay_intact():
    text = "[лекция](https://example.com/a_b_c) и https://site.kz/x_y_z"
    assert markdown_to_html(text) == (
        '<a href="https://example.com/a_b_c">лекция</a> и https://site.kz/x_y_z'
    )


def test_unpaired_star_is_left_alone():
    assert markdown_to_html("5 * 3 = 15") == "5 * 3 = 15"


def test_italic():
    assert markdown_to_html("это *важно*") == "это <i>важно</i>"


def test_split_keeps_paragraphs():
    text = "а" * 30 + "\n\n" + "б" * 30
    assert split_message(text, limit=40) == ["а" * 30, "б" * 30]
    assert split_message("короткий") == ["короткий"]


def test_strip_markdown_fallback():
    assert strip_markdown("**жирный**\n- пункт") == "жирный\n• пункт"

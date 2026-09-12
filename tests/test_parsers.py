from novel_scraper.parsers import (
    html_fragment_to_text,
    strip_leading_chapter_heading,
    strip_page_marker,
)


def test_html_fragment_to_text_preserves_paragraph_breaks() -> None:
    fragment = "<div><script>bad()</script>第一段<br /><br />第二段</div>"
    assert html_fragment_to_text(fragment) == "第一段\n\n第二段"


def test_strip_leading_chapter_heading() -> None:
    text = "第1164章 第一千一百五十三 易位杀伤\n\n正文第一段"
    assert strip_leading_chapter_heading(text) == "正文第一段"


def test_strip_page_marker() -> None:
    assert strip_page_marker("第1156章 标题(第/页)") == "第1156章 标题"

from __future__ import annotations

import pytest

from novel_scraper.adapters import (
    BqgAdapter,
    DeqixsAdapter,
    GenericAdapter,
    SuduguAdapter,
    adapter_for_url,
)
from novel_scraper.exceptions import ChapterContentError, ParseError
from novel_scraper.models import Book, Chapter, FetchedPage

BOOK_HTML = """
<html><head><title>\u6d4b\u8bd5\u5c0f\u8bf4</title></head><body>
<h1>\u6d4b\u8bd5\u5c0f\u8bf4</h1><div class="author">\u4f5c\u8005\uff1a\u6d4b\u8bd5\u4f5c\u8005</div>
<div id="catalog"><a href="/chapter/1.html">\u7b2c\u4e00\u7ae0 \u5f00\u59cb</a>
<a href="/chapter/2.html">\u7b2c\u4e8c\u7ae0 \u7ee7\u7eed</a></div>
</body></html>
"""
CHAPTER_HTML = """
<html><body><h1>\u7b2c\u4e00\u7ae0 \u5f00\u59cb</h1>
<div id="content"><p>\u8fd9\u662f\u6b63\u6587\u7b2c\u4e00\u6bb5\u3002</p><p>\u8fd9\u662f\u6b63\u6587\u7b2c\u4e8c\u6bb5\u3002</p></div></body></html>
"""


class FakeHttp:
    def __init__(self, response: str = CHAPTER_HTML) -> None:
        self.response = response
        self.requested: list[str] = []

    def get_text(self, url: str, **_kwargs) -> str:
        self.requested.append(url)
        return self.response


def test_unknown_http_url_uses_generic_fallback() -> None:
    adapter = adapter_for_url("https://novel.example/book/", FakeHttp())
    assert isinstance(adapter, GenericAdapter)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.deqixs.cc/books/99/", DeqixsAdapter),
        ("https://www.sudugu.cc/674/", SuduguAdapter),
        ("https://www.bqg616.cc/#/book/717/", BqgAdapter),
    ],
)
def test_specific_adapters_have_priority(url: str, expected: type) -> None:
    adapter = adapter_for_url(url, FakeHttp())
    assert isinstance(adapter, expected)


def test_fixture_parses_title_author_and_chapter_links() -> None:
    adapter = GenericAdapter(FakeHttp())
    book = adapter.parse_book(BOOK_HTML, "https://novel.example/book/")

    assert isinstance(book, Book)
    assert book.title == "\u6d4b\u8bd5\u5c0f\u8bf4"
    assert book.author == "\u6d4b\u8bd5\u4f5c\u8005"
    assert len(book.chapters) == 2
    assert all(isinstance(chapter, Chapter) for chapter in book.chapters)
    assert book.chapters[0].url == "https://novel.example/chapter/1.html"


def test_fixture_fetches_chapter_body() -> None:
    adapter = GenericAdapter(FakeHttp())
    chapter = Chapter(1, "\u7b2c\u4e00\u7ae0", "https://novel.example/chapter/1.html")

    pages = adapter.fetch_chapter_pages(chapter, max_pages=5)

    assert pages == (FetchedPage(1, chapter.url, "\u8fd9\u662f\u6b63\u6587\u7b2c\u4e00\u6bb5\u3002\n\u8fd9\u662f\u6b63\u6587\u7b2c\u4e8c\u6bb5\u3002"),)


def test_missing_chapter_list_has_clear_parse_error() -> None:
    adapter = GenericAdapter(FakeHttp())
    with pytest.raises(ParseError, match="\u65e0\u6cd5\u627e\u5230\u7ae0\u8282\u5217\u8868"):
        adapter.parse_book("<h1>\u4e00\u672c\u4e66</h1>", "https://novel.example/book/")


def test_missing_content_has_clear_error() -> None:
    adapter = GenericAdapter(FakeHttp("<html><body><p>\u666e\u901a\u6587\u672c</p></body></html>"))
    chapter = Chapter(1, "\u7b2c\u4e00\u7ae0", "https://novel.example/chapter/1.html")
    with pytest.raises(ChapterContentError, match="\u65e0\u6cd5\u5b9a\u4f4d\u6b63\u6587\u533a\u57df"):
        adapter.fetch_chapter_pages(chapter, max_pages=1)

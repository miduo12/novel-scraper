from __future__ import annotations

import pytest

from novel_scraper.adapters import BqgAdapter, adapter_for_url, is_supported_url
from novel_scraper.exceptions import ParseError
from novel_scraper.models import Book, Chapter, FetchedPage

BOOK = {
    "id": "717",
    "title": "斗破苍穹",
    "author": "天蚕土豆",
    "intro": "一个关于斗气的故事。",
}
CHAPTER_NAMES = [
    "上架感言",
    "土豆三江访谈感言",
    "斗破苍穹人物出场表",
    "四章完毕",
    "游戏授权消息",
    "作品相关",
    "第一章 陨落的天才",
]
CHAPTER = {
    "id": 717,
    "chapterid": 7,
    "title": "斗破苍穹",
    "chaptername": "第一章 陨落的天才",
    "txt": "第一段正文。\n第二段正文。",
}


class FakeHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def get_json(self, url: str, *, headers=None, params=None):
        self.calls.append((url, params))
        if url.endswith("/api/book"):
            return BOOK
        if url.endswith("/api/booklist"):
            return {"list": CHAPTER_NAMES}
        if url.endswith("/api/chapter"):
            return CHAPTER
        raise AssertionError(f"Unexpected URL: {url}")


def test_bqg_url_is_recognized_and_registered() -> None:
    assert is_supported_url("https://www.bqg616.cc/#/book/717/")
    assert isinstance(adapter_for_url("https://www.bqg616.cc/#/book/717/", FakeHttp()), BqgAdapter)


def test_normalize_book_url_from_chapter_routes() -> None:
    adapter = BqgAdapter(FakeHttp())
    assert (
        adapter.normalize_book_url("https://www.bqg616.cc/#/book/717/7_2.html")
        == "https://www.bqg616.cc/#/book/717/"
    )
    assert (
        adapter.normalize_book_url("https://m.bqg616.cc/book/717/7.html")
        == "https://m.bqg616.cc/#/book/717/"
    )


def test_parse_book_returns_shared_models() -> None:
    adapter = BqgAdapter(FakeHttp())
    book = adapter.parse_book("<div id='app'></div>", "https://www.bqg616.cc/#/book/717/")

    assert isinstance(book, Book)
    assert book.title == "斗破苍穹"
    assert book.author == "天蚕土豆"
    assert len(book.chapters) == len(CHAPTER_NAMES)
    assert isinstance(book.chapters[6], Chapter)
    assert book.chapters[6].number == 1
    assert book.chapters[6].url.endswith("/book/717/7.html")


def test_fetch_chapter_returns_page_model_and_known_api_token() -> None:
    http = FakeHttp()
    adapter = BqgAdapter(http)
    chapter = Chapter(
        index=7,
        title="第一章 陨落的天才",
        url="https://www.bqg616.cc/#/book/717/7.html",
        number=1,
    )

    pages = adapter.fetch_chapter_pages(chapter, max_pages=10)

    assert len(pages) == 1
    assert isinstance(pages[0], FetchedPage)
    assert pages[0].content == "第一段正文。\n第二段正文。"
    assert http.calls[-1][1] == {"token": "6CJGbsTyoroA5ZL5yt5GIVqp5hYeww3LfmXgSY0+APo="}


def test_unknown_domain_does_not_match() -> None:
    assert not BqgAdapter.matches("https://notbqg616.cc/book/717/")
    assert not is_supported_url("https://example.org/book/717/")


def test_homepage_without_book_id_cannot_be_normalized() -> None:
    with pytest.raises(ParseError, match="提取书籍 ID"):
        BqgAdapter(FakeHttp()).normalize_book_url("https://www.bqg616.cc/")

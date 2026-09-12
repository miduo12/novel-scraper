import os

import pytest

from novel_scraper.crawler import CrawlOptions, NovelCrawler

pytestmark = pytest.mark.integration


@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="需要显式设置 RUN_LIVE_TESTS=1")
def test_live_directory_and_chapter() -> None:
    options = CrawlOptions(delay=0.1, timeout=20, retries=1, max_pages=5)
    with NovelCrawler.from_url("https://www.deqixs.cc/books/99/", options) as crawler:
        book = crawler.fetch_book("https://www.deqixs.cc/books/99/")
        assert book.title == "玄鉴仙族"
        assert len(book.chapters) > 1000
        chapter = next(item for item in book.chapters if item.url.endswith("/63332.html"))
        pages = crawler.adapter.fetch_chapter_pages(chapter, max_pages=5)
        assert pages
        assert pages[0].content

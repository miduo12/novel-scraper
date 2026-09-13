import os

import pytest

from novel_scraper.crawler import CrawlOptions, NovelCrawler

pytestmark = pytest.mark.integration


@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="需要显式设置 RUN_LIVE_TESTS=1")
def test_live_sudugu_directory_and_first_chapter() -> None:
    options = CrawlOptions(delay=0.1, timeout=30, retries=1)
    with NovelCrawler.from_url("https://www.sudugu.cc/674/", options) as crawler:
        book = crawler.fetch_book("https://www.sudugu.cc/674/")
        assert book.title == "阵问长生"
        assert book.author == "观虚"
        assert len(book.chapters) > 900
        pages = crawler.adapter.fetch_chapter_pages(book.chapters[0], max_pages=10)
        assert len(pages) >= 2
        assert "".join(page.content for page in pages).strip()

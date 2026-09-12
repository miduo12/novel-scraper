import os
from pathlib import Path

import pytest

from novel_scraper.crawler import CrawlOptions, NovelCrawler
from novel_scraper.text_cleaner import BookCleaner, CleaningMode

pytestmark = pytest.mark.integration


@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="需要显式设置 RUN_LIVE_TESTS=1")
def test_live_chapter_can_be_cleaned_without_modifying_original(tmp_path: Path) -> None:
    options = CrawlOptions(
        output_dir=tmp_path,
        delay=0.1,
        retries=1,
        start_chapter=1,
        end_chapter=1,
    )
    with NovelCrawler.from_url("https://www.deqixs.cc/books/99/", options) as crawler:
        crawler.crawl_book("https://www.deqixs.cc/books/99/")

    book_dir = tmp_path / "玄鉴仙族"
    original_files = {
        path.name: path.read_text(encoding="utf-8")
        for path in (book_dir / "chapters").glob("*.txt")
    }
    result = BookCleaner().process(book_dir, CleaningMode.AUTO)

    assert result.chapter_count == 1
    assert result.reports_dir and result.reports_dir.exists()
    assert result.cleaned_book_path and result.cleaned_book_path.exists()
    for name, original in original_files.items():
        assert (book_dir / "chapters" / name).read_text(encoding="utf-8") == original

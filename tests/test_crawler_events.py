from pathlib import Path
from threading import Event

import pytest

from novel_scraper.crawler import CrawlOptions, NovelCrawler
from novel_scraper.exceptions import CrawlCancelled
from novel_scraper.models import Book, Chapter, FetchedPage


class FakeHttp:
    def get_text(self, url: str) -> str:
        return "<html></html>"

    def close(self) -> None:
        pass


class FakeAdapter:
    name = "fake"

    def __init__(self, chapter_count: int = 1) -> None:
        self.http = FakeHttp()
        self.chapters = tuple(
            Chapter(
                index=index,
                title=f"第{index}章",
                url=f"https://example.com/{index}.html",
            )
            for index in range(1, chapter_count + 1)
        )

    def normalize_book_url(self, url: str) -> str:
        return "https://example.com/book/"

    def parse_book(self, html: str, source_url: str) -> Book:
        return Book(
            title="测试书",
            author="测试作者",
            description="",
            source_url=source_url,
            chapters=self.chapters,
        )

    def fetch_chapter_pages(self, chapter, max_pages, *, on_page=None, should_cancel=None):
        if on_page:
            on_page(1)
        if should_cancel and should_cancel():
            raise CrawlCancelled("用户已停止抓取")
        return (FetchedPage(number=1, url=chapter.url, content=f"{chapter.title}正文"),)


def make_crawler(
    tmp_path: Path,
    callback,
    cancel_event=None,
    *,
    options: CrawlOptions | None = None,
    chapter_count: int = 1,
) -> NovelCrawler:
    return NovelCrawler(
        FakeAdapter(chapter_count),
        options or CrawlOptions(output_dir=tmp_path),
        progress_callback=callback,
        cancel_event=cancel_event,
    )


def test_crawler_emits_progress_events(tmp_path: Path) -> None:
    events = []
    crawler = make_crawler(tmp_path, events.append)
    result = crawler.crawl_book("https://example.com/book/1.html")

    assert result.completed == 1
    assert result.output_path.exists()
    assert result.chapters_path.exists()
    assert [event.kind for event in events] == [
        "book_loaded",
        "chapter_started",
        "page_started",
        "chapter_completed",
        "finished",
    ]


def test_crawler_downloads_only_selected_chapter_range(tmp_path: Path) -> None:
    events = []
    options = CrawlOptions(output_dir=tmp_path, start_chapter=2, end_chapter=4)
    crawler = make_crawler(tmp_path, events.append, options=options, chapter_count=5)
    result = crawler.crawl_book("https://example.com/book/1.html")

    started = [event.chapter_title for event in events if event.kind == "chapter_started"]
    assert started == ["第2章", "第3章", "第4章"]
    assert result.completed == 3
    assert result.output_path.exists()
    combined = result.output_path.read_text(encoding="utf-8")
    assert "第2章正文" in combined
    assert "第3章正文" in combined
    assert "第4章正文" in combined
    assert "第1章正文" not in combined
    assert "第5章正文" not in combined


def test_crawler_can_be_cancelled(tmp_path: Path) -> None:
    events = []
    cancel_event = Event()
    cancel_event.set()
    crawler = make_crawler(tmp_path, events.append, cancel_event)

    with pytest.raises(CrawlCancelled):
        crawler.crawl_book("https://example.com/book/1.html")

    assert events[-1].kind == "cancelled"

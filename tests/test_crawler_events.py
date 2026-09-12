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

    def __init__(self) -> None:
        self.http = FakeHttp()
        self.chapter = Chapter(index=1, title="第1章", url="https://example.com/1.html")

    def normalize_book_url(self, url: str) -> str:
        return "https://example.com/book/"

    def parse_book(self, html: str, source_url: str) -> Book:
        return Book(
            title="测试书",
            author="测试作者",
            description="",
            source_url=source_url,
            chapters=(self.chapter,),
        )

    def fetch_chapter_pages(self, chapter, max_pages, *, on_page=None, should_cancel=None):
        if on_page:
            on_page(1)
        if should_cancel and should_cancel():
            raise CrawlCancelled("用户已停止抓取")
        return (FetchedPage(number=1, url=chapter.url, content="正文"),)


def make_crawler(tmp_path: Path, callback, cancel_event=None) -> NovelCrawler:
    return NovelCrawler(
        FakeAdapter(),
        CrawlOptions(output_dir=tmp_path),
        progress_callback=callback,
        cancel_event=cancel_event,
    )


def test_crawler_emits_progress_events(tmp_path: Path) -> None:
    events = []
    crawler = make_crawler(tmp_path, events.append)
    result = crawler.crawl_book("https://example.com/book/1.html")

    assert result.completed == 1
    assert [event.kind for event in events] == [
        "book_loaded",
        "chapter_started",
        "page_started",
        "chapter_completed",
        "finished",
    ]


def test_crawler_can_be_cancelled(tmp_path: Path) -> None:
    events = []
    cancel_event = Event()
    cancel_event.set()
    crawler = make_crawler(tmp_path, events.append, cancel_event)

    with pytest.raises(CrawlCancelled):
        crawler.crawl_book("https://example.com/book/1.html")

    assert events[-1].kind == "cancelled"

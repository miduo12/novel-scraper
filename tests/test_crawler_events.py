from pathlib import Path
from threading import Event

from novel_scraper.crawler import CrawlOptions, NovelCrawler
from novel_scraper.models import Book, Chapter, FetchedPage


class FakeHttp:
    def get_text(self, url: str) -> str:
        return "<html></html>"

    def close(self) -> None:
        pass


class FakeAdapter:
    name = "fake"

    def __init__(
        self,
        chapter_count: int = 1,
        chapter_numbers: tuple[int, ...] | None = None,
        cancel_event: Event | None = None,
        cancel_after_fetch: bool = False,
    ) -> None:
        self.http = FakeHttp()
        self.cancel_event = cancel_event
        self.cancel_after_fetch = cancel_after_fetch
        numbers = chapter_numbers or tuple(range(1, chapter_count + 1))
        self.chapters = tuple(
            Chapter(
                index=index,
                title=f"第{numbers[index - 1]}章",
                url=f"https://example.com/{index}.html",
                number=numbers[index - 1],
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
        result = (FetchedPage(number=1, url=chapter.url, content=f"{chapter.title}正文"),)
        if self.cancel_event is not None and self.cancel_after_fetch:
            self.cancel_event.set()
        return result


def make_crawler(
    tmp_path: Path,
    callback,
    cancel_event=None,
    *,
    options: CrawlOptions | None = None,
    chapter_count: int = 1,
    chapter_numbers: tuple[int, ...] | None = None,
    cancel_after_fetch: bool = False,
    adapter=None,
) -> NovelCrawler:
    selected_adapter = adapter or FakeAdapter(
        chapter_count,
        chapter_numbers,
        cancel_event=cancel_event,
        cancel_after_fetch=cancel_after_fetch,
    )
    return NovelCrawler(
        selected_adapter,
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
    options = CrawlOptions(output_dir=tmp_path, start_chapter=3, end_chapter=7)
    crawler = make_crawler(
        tmp_path,
        events.append,
        options=options,
        chapter_count=5,
        chapter_numbers=(1, 3, 5, 7, 9),
    )
    result = crawler.crawl_book("https://example.com/book/1.html")

    started = [event.chapter_title for event in events if event.kind == "chapter_started"]
    assert started == ["第3章", "第5章", "第7章"]
    assert result.completed == 3
    assert result.output_path.exists()
    combined = result.output_path.read_text(encoding="utf-8")
    assert "第3章正文" in combined
    assert "第5章正文" in combined
    assert "第7章正文" in combined
    assert "第1章正文" not in combined
    assert "第9章正文" not in combined


def test_crawler_can_be_cancelled_before_start(tmp_path: Path) -> None:
    events = []
    cancel_event = Event()
    cancel_event.set()
    crawler = make_crawler(tmp_path, events.append, cancel_event)

    result = crawler.crawl_book("https://example.com/book/1.html")

    assert result.cancelled is True
    assert result.completed == 0
    assert events[-1].kind == "cancelled"


def test_crawler_finishes_current_chapter_before_stopping(tmp_path: Path) -> None:
    events = []
    cancel_event = Event()
    crawler = make_crawler(
        tmp_path,
        events.append,
        cancel_event,
        chapter_count=3,
        cancel_after_fetch=True,
    )

    result = crawler.crawl_book("https://example.com/book/1.html")

    assert result.cancelled is True
    assert result.completed == 1
    assert [event.chapter_title for event in events if event.kind == "chapter_started"] == ["第1章"]
    assert events[-1].kind == "cancelled"
    assert result.output_path.exists()
    assert "第1章正文" in result.output_path.read_text(encoding="utf-8")


class DuplicateContentAdapter(FakeAdapter):
    def fetch_chapter_pages(self, chapter, max_pages, *, on_page=None, should_cancel=None):
        if on_page:
            on_page(1)
        return (FetchedPage(number=1, url=chapter.url, content="完全相同的正文"),)


def test_crawler_skips_duplicate_content(tmp_path: Path) -> None:
    events = []
    crawler = make_crawler(
        tmp_path,
        events.append,
        chapter_count=3,
        adapter=DuplicateContentAdapter(chapter_count=3),
    )
    result = crawler.crawl_book("https://example.com/book/1.html")

    assert result.completed == 1
    assert result.duplicates == 2
    assert len(list(result.chapters_path.glob("*.txt"))) == 1
    assert (tmp_path / "测试书" / "duplicate_chapters.txt").exists()
    assert [event.kind for event in events].count("chapter_duplicate") == 2


def test_crawler_can_download_in_reverse_order(tmp_path: Path) -> None:
    events = []
    options = CrawlOptions(output_dir=tmp_path, reverse=True, deduplicate=False)
    crawler = make_crawler(
        tmp_path,
        events.append,
        options=options,
        chapter_count=3,
    )
    result = crawler.crawl_book("https://example.com/book/1.html")

    started = [event.chapter_title for event in events if event.kind == "chapter_started"]
    assert started == ["第3章", "第2章", "第1章"]
    combined = result.output_path.read_text(encoding="utf-8")
    assert combined.index("第1章正文") < combined.index("第2章正文") < combined.index("第3章正文")

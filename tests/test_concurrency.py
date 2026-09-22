import time
from pathlib import Path

from novel_scraper.crawler import CrawlOptions, NovelCrawler
from novel_scraper.models import Book, Chapter, FetchedPage


class FakeHttp:
    def get_text(self, url: str) -> str:
        return "<html></html>"

    def close(self) -> None:
        pass


class TimedAdapter:
    def __init__(self, count: int = 6, fail_index: int | None = None) -> None:
        self.http = FakeHttp()
        self.fail_index = fail_index
        self.chapters = tuple(
            Chapter(index=i, title=f"第{i}章", url=f"https://example.com/{i}.html", number=i)
            for i in range(1, count + 1)
        )

    def normalize_book_url(self, url: str) -> str:
        return "https://example.com/book/"

    def parse_book(self, html: str, source_url: str) -> Book:
        return Book("并发测试", "作者", "", source_url, self.chapters)

    def fetch_chapter_pages(self, chapter, max_pages, *, on_page=None, should_cancel=None):
        if chapter.index == self.fail_index:
            raise RuntimeError("模拟失败")
        time.sleep(0.06 if chapter.index == 1 else 0.01)
        if on_page:
            on_page(1)
        return (FetchedPage(1, chapter.url, f"{chapter.title}正文"),)


def run_download(tmp_path: Path, workers: int, fail_index: int | None = None):
    options = CrawlOptions(
        output_dir=tmp_path,
        delay=0.0,
        jitter=0.0,
        max_workers=workers,
        deduplicate=False,
    )
    crawler = NovelCrawler(TimedAdapter(fail_index=fail_index), options)
    started = time.perf_counter()
    result = crawler.crawl_book("https://example.com/book/")
    return result, time.perf_counter() - started


def test_concurrent_results_keep_txt_order(tmp_path: Path) -> None:
    result, _elapsed = run_download(tmp_path, workers=5)
    combined = result.output_path.read_text(encoding="utf-8")
    positions = [combined.index(f"第{i}章正文") for i in range(1, 7)]
    assert positions == sorted(positions)
    assert result.completed == 6


def test_concurrent_download_is_faster_than_serial(tmp_path: Path) -> None:
    _serial_result, serial_elapsed = run_download(tmp_path / "serial", workers=1)
    _parallel_result, parallel_elapsed = run_download(tmp_path / "parallel", workers=5)
    assert parallel_elapsed < serial_elapsed


def test_one_failed_chapter_does_not_stop_others(tmp_path: Path) -> None:
    result, _elapsed = run_download(tmp_path, workers=5, fail_index=3)
    assert result.completed == 5
    assert result.failed == 1
    combined = result.output_path.read_text(encoding="utf-8")
    assert "第1章正文" in combined
    assert "第3章正文" not in combined
    assert "第6章正文" in combined
    assert (tmp_path / "并发测试" / "failed_chapters.txt").exists()


def test_concurrent_resume_skips_completed_chapters(tmp_path: Path) -> None:
    first_result, _elapsed = run_download(tmp_path, workers=5)
    assert first_result.completed == 6

    second_result, _elapsed = run_download(tmp_path, workers=5)
    assert second_result.completed == 0
    assert second_result.skipped == 6

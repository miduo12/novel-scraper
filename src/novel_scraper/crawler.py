from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .adapters import SiteAdapter, adapter_for_url
from .http import HttpClient
from .models import Book, Chapter, CrawlResult
from .storage import BookStorage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlOptions:
    output_dir: Path = Path("downloads")
    delay: float = 1.0
    timeout: float = 20.0
    retries: int = 3
    max_pages: int = 100
    limit: int | None = None
    force: bool = False


class NovelCrawler:
    def __init__(self, adapter: SiteAdapter, options: CrawlOptions) -> None:
        self.adapter = adapter
        self.options = options
        self.http = adapter.http

    @classmethod
    def from_url(cls, url: str, options: CrawlOptions) -> "NovelCrawler":
        http = HttpClient(
            delay=options.delay,
            timeout=options.timeout,
            retries=options.retries,
        )
        return cls(adapter_for_url(url, http), options)

    def __enter__(self) -> "NovelCrawler":
        return self

    def __exit__(self, *_: object) -> None:
        self.http.close()

    def fetch_book(self, url: str) -> Book:
        book_url = self.adapter.normalize_book_url(url)
        html = self.http.get_text(book_url)
        return self.adapter.parse_book(html, book_url)

    def list_chapters(self, url: str) -> Book:
        return self.fetch_book(url)

    def crawl_book(self, url: str) -> CrawlResult:
        book = self.fetch_book(url)
        chapters = book.chapters
        if self.options.limit is not None:
            chapters = chapters[: max(0, self.options.limit)]

        storage = BookStorage(self.options.output_dir, book)
        state = storage.load_state()
        completed = 0
        skipped = 0
        failed = 0

        logger.info(
            "《%s》 作者：%s，共 %d 章，本次处理 %d 章",
            book.title,
            book.author or "未知",
            len(book.chapters),
            len(chapters),
        )

        for position, chapter in enumerate(chapters, start=1):
            path = storage.chapter_path(chapter)
            if not self.options.force and chapter.url in state.completed and path.exists():
                skipped += 1
                logger.info("[%d/%d] %s，已存在，跳过", position, len(chapters), chapter.title)
                continue

            logger.info("[%d/%d] %s", position, len(chapters), chapter.title)
            try:
                pages = self.adapter.fetch_chapter_pages(chapter, self.options.max_pages)
                content = "\n\n".join(page.content for page in pages)
                storage.save_chapter(chapter, content)
                storage.mark_completed(state, chapter)
                completed += 1
                logger.info("    完成，共 %d 页", len(pages))
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                failed += 1
                reason = str(exc) or exc.__class__.__name__
                storage.mark_failed(state, chapter, reason)
                logger.error("    失败：%s", reason)
                logger.debug("章节抓取异常", exc_info=True)

        failure_path = storage.write_failures(state)
        output_path = storage.build_combined_txt()
        logger.info(
            "运行结束：新增 %d，跳过 %d，失败 %d；TXT：%s",
            completed,
            skipped,
            failed,
            output_path,
        )
        if failure_path:
            logger.warning("失败章节已记录：%s", failure_path)

        return CrawlResult(
            book=book,
            output_path=output_path,
            completed=completed,
            skipped=skipped,
            failed=failed,
        )

    def crawl_single_chapter(self, url: str) -> tuple[Chapter, Path]:
        book = self.fetch_book(url)
        chapter = next(
            (item for item in book.chapters if item.url.rstrip("/") == url.rstrip("/")),
            None,
        )
        if chapter is None:
            page_html = self.http.get_text(url)
            chapter = Chapter(
                index=1,
                title=self.adapter.parse_chapter_title(page_html) or "单章",
                url=url,
            )

        logger.info("抓取单章：%s", chapter.title)
        pages = self.adapter.fetch_chapter_pages(chapter, self.options.max_pages)
        content = "\n\n".join(page.content for page in pages)
        storage = BookStorage(self.options.output_dir, book)
        path = storage.save_chapter(chapter, content)
        logger.info("完成，共 %d 页；文件：%s", len(pages), path)
        return chapter, path

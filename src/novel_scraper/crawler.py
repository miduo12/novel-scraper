from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from .adapters import SiteAdapter, adapter_for_url
from .events import CrawlEvent, ProgressCallback
from .exceptions import CrawlCancelled
from .http import HttpClient
from .models import Book, Chapter, CrawlResult
from .storage import BookStorage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlOptions:
    output_dir: Path = Path("downloads")
    delay: float = 0.2
    timeout: float = 20.0
    retries: int = 3
    max_pages: int = 100
    limit: int | None = None
    force: bool = False


class NovelCrawler:
    def __init__(
        self,
        adapter: SiteAdapter,
        options: CrawlOptions,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_event: Event | None = None,
    ) -> None:
        self.adapter = adapter
        self.options = options
        self.http = adapter.http
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event

    @classmethod
    def from_url(
        cls,
        url: str,
        options: CrawlOptions,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_event: Event | None = None,
    ) -> "NovelCrawler":
        http = HttpClient(
            delay=options.delay,
            timeout=options.timeout,
            retries=options.retries,
        )
        return cls(
            adapter_for_url(url, http),
            options,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )

    def __enter__(self) -> "NovelCrawler":
        return self

    def __exit__(self, *_: object) -> None:
        self.http.close()

    def _emit(
        self,
        kind: str,
        message: str = "",
        *,
        book: Book | None = None,
        chapter: Chapter | None = None,
        completed: int = 0,
        total: int = 0,
        failed: int = 0,
        page: int = 0,
        output_path: Path | None = None,
    ) -> None:
        if self.progress_callback is None:
            return
        event = CrawlEvent(
            kind=kind,  # type: ignore[arg-type]
            message=message,
            book_title=book.title if book is not None else "",
            author=book.author if book is not None else "",
            chapter_title=chapter.title if chapter is not None else "",
            completed=completed,
            total=total,
            failed=failed,
            page=page,
            output_path=output_path,
        )
        try:
            self.progress_callback(event)
        except Exception:
            logger.debug("进度回调异常", exc_info=True)

    def _cancelled(self) -> bool:
        return self.cancel_event is not None and self.cancel_event.is_set()

    def _raise_if_cancelled(self, book: Book | None = None, total: int = 0) -> None:
        if not self._cancelled():
            return
        self._emit("cancelled", "已停止下载，当前进度已保存", book=book, total=total)
        raise CrawlCancelled("用户已停止抓取")

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
        total = len(chapters)

        logger.info(
            "《%s》 作者：%s，共 %d 章，本次处理 %d 章",
            book.title,
            book.author or "未知",
            len(book.chapters),
            total,
        )
        self._emit(
            "book_loaded",
            f"《{book.title}》 作者：{book.author or '未知'}，本次处理 {total} 章",
            book=book,
            total=total,
        )

        for position, chapter in enumerate(chapters, start=1):
            self._raise_if_cancelled(book, total)
            path = storage.chapter_path(chapter)
            if not self.options.force and chapter.url in state.completed and path.exists():
                skipped += 1
                logger.info("[%d/%d] %s，已存在，跳过", position, total, chapter.title)
                self._emit(
                    "chapter_skipped",
                    chapter.title,
                    book=book,
                    chapter=chapter,
                    completed=position,
                    total=total,
                    failed=failed,
                )
                continue

            logger.info("[%d/%d] %s", position, total, chapter.title)
            self._emit(
                "chapter_started",
                chapter.title,
                book=book,
                chapter=chapter,
                completed=position - 1,
                total=total,
                failed=failed,
            )
            try:
                pages = self.adapter.fetch_chapter_pages(
                    chapter,
                    self.options.max_pages,
                    on_page=lambda page_number: self._emit(
                        "page_started",
                        f"正在下载第 {page_number} 页",
                        book=book,
                        chapter=chapter,
                        completed=position - 1,
                        total=total,
                        failed=failed,
                        page=page_number,
                    ),
                    should_cancel=self._cancelled,
                )
                content = "\n\n".join(page.content for page in pages)
                storage.save_chapter(chapter, content)
                storage.mark_completed(state, chapter)
                completed += 1
                logger.info("    完成，共 %d 页", len(pages))
                self._emit(
                    "chapter_completed",
                    f"完成，共 {len(pages)} 页",
                    book=book,
                    chapter=chapter,
                    completed=position,
                    total=total,
                    failed=failed,
                )
            except CrawlCancelled:
                raise
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                failed += 1
                reason = str(exc) or exc.__class__.__name__
                storage.mark_failed(state, chapter, reason)
                logger.error("    失败：%s", reason)
                logger.debug("章节抓取异常", exc_info=True)
                self._emit(
                    "chapter_failed",
                    reason,
                    book=book,
                    chapter=chapter,
                    completed=position,
                    total=total,
                    failed=failed,
                )

        self._raise_if_cancelled(book, total)
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
        self._emit(
            "finished",
            f"下载完成：新增 {completed}，跳过 {skipped}，失败 {failed}",
            book=book,
            completed=total,
            total=total,
            failed=failed,
            output_path=output_path,
        )

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
        self._emit(
            "chapter_started",
            chapter.title,
            book=book,
            chapter=chapter,
            completed=0,
            total=1,
        )
        pages = self.adapter.fetch_chapter_pages(
            chapter,
            self.options.max_pages,
            on_page=lambda page_number: self._emit(
                "page_started",
                f"正在下载第 {page_number} 页",
                book=book,
                chapter=chapter,
                completed=0,
                total=1,
                page=page_number,
            ),
            should_cancel=self._cancelled,
        )
        content = "\n\n".join(page.content for page in pages)
        storage = BookStorage(self.options.output_dir, book)
        path = storage.save_chapter(chapter, content)
        logger.info("完成，共 %d 页；文件：%s", len(pages), path)
        self._emit(
            "finished",
            f"单章下载完成，共 {len(pages)} 页",
            book=book,
            chapter=chapter,
            completed=1,
            total=1,
            output_path=path,
        )
        return chapter, path

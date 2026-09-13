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
from .utils import content_hash

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlOptions:
    output_dir: Path = Path("downloads")
    delay: float = 0.2
    timeout: float = 20.0
    retries: int = 3
    max_pages: int = 100
    limit: int | None = None
    start_chapter: int | None = None
    end_chapter: int | None = None
    force: bool = False
    deduplicate: bool = True
    reverse: bool = False


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
    ) -> NovelCrawler:
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

    def __enter__(self) -> NovelCrawler:  # noqa: PYI034
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
        book_total: int = 0,
        first_chapter_number: int | None = None,
        last_chapter_number: int | None = None,
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
            book_total=book_total,
            first_chapter_number=first_chapter_number,
            last_chapter_number=last_chapter_number,
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

    def fetch_book(self, url: str) -> Book:
        book_url = self.adapter.normalize_book_url(url)
        html = self.http.get_text(book_url)
        return self.adapter.parse_book(html, book_url)

    def list_chapters(self, url: str) -> Book:
        return self.fetch_book(url)

    def _select_chapters(self, book: Book) -> tuple[Chapter, ...]:
        start = self.options.start_chapter
        end = self.options.end_chapter
        if start is None and end is None:
            return book.chapters

        numbered = [chapter for chapter in book.chapters if chapter.number is not None]
        if numbered:
            first_number = min(chapter.number for chapter in numbered if chapter.number is not None)
            last_number = max(chapter.number for chapter in numbered if chapter.number is not None)
            start_number = start if start is not None else first_number
            end_number = end if end is not None else last_number
            if start_number < 1:
                raise ValueError("起始章节必须大于或等于 1")
            if end_number < start_number:
                raise ValueError("结束章节不能小于起始章节")
            selected = [
                chapter
                for chapter in numbered
                if chapter.number is not None and start_number <= chapter.number <= end_number
            ]
            if not selected:
                raise ValueError(
                    f"所选章节范围不在目录中，当前章号范围：{first_number}-{last_number}"
                )
            first_index = min(chapter.index for chapter in selected)
            last_index = max(chapter.index for chapter in selected)
            return tuple(
                chapter for chapter in book.chapters if first_index <= chapter.index <= last_index
            )

        total_chapters = len(book.chapters)
        start_index = start or 1
        end_index = end or total_chapters
        if start_index < 1:
            raise ValueError("起始章节必须大于或等于 1")
        if end_index < start_index:
            raise ValueError("结束章节不能小于起始章节")
        if start_index > total_chapters:
            raise ValueError(f"起始章节超出目录范围，当前共 {total_chapters} 章")
        return book.chapters[start_index - 1 : min(end_index, total_chapters)]

    def crawl_book(self, url: str) -> CrawlResult:
        book = self.fetch_book(url)
        total_chapters = len(book.chapters)
        numbered = [chapter.number for chapter in book.chapters if chapter.number is not None]
        first_number = min(numbered) if numbered else None
        last_number = max(numbered) if numbered else None
        chapters = self._select_chapters(book)
        if self.options.limit is not None:
            chapters = chapters[: max(0, self.options.limit)]
        if self.options.reverse:
            chapters = tuple(reversed(chapters))

        storage = BookStorage(self.options.output_dir, book)
        state = storage.load_state()
        completed = 0
        skipped = 0
        duplicates = 0
        failed = 0
        cancelled = False
        total = len(chapters)
        hash_index: dict[str, tuple[str, str]] = {}
        if self.options.deduplicate:
            for existing_chapter in book.chapters:
                existing_path = storage.chapter_path(existing_chapter)
                if existing_path.exists():
                    digest = content_hash(existing_path.read_text(encoding="utf-8"))
                    hash_index.setdefault(
                        digest,
                        (existing_chapter.title, existing_chapter.url),
                    )
            for duplicate_url, duplicate in state.duplicates.items():
                digest = duplicate.get("hash", "")
                if digest:
                    hash_index.setdefault(
                        digest,
                        (duplicate.get("first_title", "未知章节"), duplicate_url),
                    )

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
            book_total=total_chapters,
            first_chapter_number=first_number,
            last_chapter_number=last_number,
        )

        for position, chapter in enumerate(chapters, start=1):
            if self._cancelled():
                cancelled = True
                break
            if self.options.deduplicate and chapter.url in state.duplicates:
                duplicates += 1
                logger.info("[%d/%d] %s，正文重复，跳过", position, total, chapter.title)
                self._emit(
                    "chapter_duplicate",
                    "与已下载章节正文重复，跳过",
                    book=book,
                    chapter=chapter,
                    completed=position,
                    total=total,
                    failed=failed,
                )
                continue
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
                    on_page=lambda page_number, chapter=chapter, position=position, failed=failed: (
                        self._emit(
                            "page_started",
                            f"正在下载第 {page_number} 页",
                            book=book,
                            chapter=chapter,
                            completed=position - 1,
                            total=total,
                            failed=failed,
                            page=page_number,
                        )
                    ),
                )
                content = "\n\n".join(page.content for page in pages)
                digest = content_hash(content)
                if self.options.deduplicate and digest in hash_index:
                    first_title, first_url = hash_index[digest]
                    duplicates += 1
                    storage.mark_duplicate(
                        state,
                        chapter,
                        digest,
                        first_title,
                        first_url,
                    )
                    logger.info(
                        "    正文与 %s 重复，跳过：%s",
                        first_title,
                        first_url,
                    )
                    self._emit(
                        "chapter_duplicate",
                        f"正文与《{first_title}》重复，跳过",
                        book=book,
                        chapter=chapter,
                        completed=position,
                        total=total,
                        failed=failed,
                    )
                    continue
                storage.save_chapter(chapter, content)
                if self.options.deduplicate:
                    hash_index[digest] = (chapter.title, chapter.url)
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

        if self._cancelled():
            cancelled = True

        failure_path = storage.write_failures(state)
        duplicate_path = storage.write_duplicates(state)
        output_path = storage.build_combined_txt()
        logger.info(
            "运行结束：新增 %d，跳过 %d，重复 %d，失败 %d；TXT：%s",
            completed,
            skipped,
            duplicates,
            failed,
            output_path,
        )
        if failure_path:
            logger.warning("失败章节已记录：%s", failure_path)
        if duplicate_path:
            logger.warning("重复章节已记录：%s", duplicate_path)
        if cancelled:
            message = "当前章节已完整保存，已在下一章开始前停止"
            self._emit(
                "cancelled",
                message,
                book=book,
                completed=sum(1 for chapter in chapters if storage.chapter_path(chapter).exists()),
                total=total,
                failed=failed,
                output_path=output_path,
            )
        else:
            self._emit(
                "finished",
                f"下载完成：新增 {completed}，跳过 {skipped}，重复 {duplicates}，失败 {failed}",
                book=book,
                completed=total,
                total=total,
                failed=failed,
                output_path=output_path,
            )

        return CrawlResult(
            book=book,
            output_path=output_path,
            chapters_path=storage.chapters_dir,
            completed=completed,
            skipped=skipped,
            duplicates=duplicates,
            failed=failed,
            cancelled=cancelled,
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

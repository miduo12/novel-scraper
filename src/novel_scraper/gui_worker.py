from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .crawler import CrawlOptions, NovelCrawler
from .exceptions import CrawlCancelled


class CrawlWorker(QThread):
    """Run the blocking crawler outside the GUI thread."""

    event_received = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(
        self,
        url: str,
        output_dir: Path,
        *,
        delay: float,
        retries: int,
        start_chapter: int | None = None,
        end_chapter: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.url = url
        self.output_dir = output_dir
        self.delay = delay
        self.retries = retries
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        options = CrawlOptions(
            output_dir=self.output_dir,
            delay=self.delay,
            timeout=20.0,
            retries=self.retries,
            max_pages=100,
            start_chapter=self.start_chapter,
            end_chapter=self.end_chapter,
        )
        try:
            with NovelCrawler.from_url(
                self.url,
                options,
                progress_callback=self.event_received.emit,
                cancel_event=self._cancel_event,
            ) as crawler:
                result = crawler.crawl_book(self.url)
            self.succeeded.emit(result)
        except CrawlCancelled:
            self.stopped.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or exc.__class__.__name__)

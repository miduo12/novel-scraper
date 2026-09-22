from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass

from .models import Chapter, FetchedPage


@dataclass(frozen=True, slots=True)
class ChapterFetchResult:
    index: int
    chapter: Chapter
    pages: tuple[FetchedPage, ...] | None = None
    error: str = ""
    duration: float = 0.0
    worker_name: str = ""


FetchChapter = Callable[[int, Chapter], ChapterFetchResult]


def ordered_chapter_results(
    chapters: list[Chapter],
    fetch_chapter: FetchChapter,
    max_workers: int,
    cancel_event: threading.Event | None = None,
) -> Iterator[ChapterFetchResult]:
    """Fetch chapters concurrently while yielding results in input order."""
    if not chapters:
        return
    workers = max(1, min(int(max_workers), 10))
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="novel-worker")
    futures: dict[Future[ChapterFetchResult], int] = {}
    buffered: dict[int, ChapterFetchResult] = {}
    cursor = 0
    next_index = 0

    def submit_next() -> None:
        nonlocal cursor
        if cursor >= len(chapters):
            return
        index = cursor
        chapter = chapters[index]
        futures[executor.submit(fetch_chapter, index, chapter)] = index
        cursor += 1

    try:
        while len(futures) < workers and cursor < len(chapters):
            submit_next()

        while futures or buffered:
            if futures:
                done, _ = wait(futures, timeout=0.25, return_when=FIRST_COMPLETED)
                for future in done:
                    index = futures.pop(future)
                    try:
                        buffered[index] = future.result()
                    except Exception as exc:  # noqa: BLE001
                        buffered[index] = ChapterFetchResult(
                            index=index,
                            chapter=chapters[index],
                            error=str(exc) or exc.__class__.__name__,
                            worker_name=threading.current_thread().name,
                        )

            stopping = cancel_event is not None and cancel_event.is_set()
            while not stopping and len(futures) < workers and cursor < len(chapters):
                submit_next()

            while next_index in buffered:
                yield buffered.pop(next_index)
                next_index += 1
            if stopping and not futures and next_index not in buffered:
                break
    finally:
        executor.shutdown(wait=True, cancel_futures=False)

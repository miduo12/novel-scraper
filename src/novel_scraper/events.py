from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

EventKind = Literal[
    "book_loaded",
    "chapter_started",
    "page_started",
    "chapter_completed",
    "chapter_skipped",
    "chapter_failed",
    "finished",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class CrawlEvent:
    kind: EventKind
    message: str = ""
    book_title: str = ""
    author: str = ""
    chapter_title: str = ""
    completed: int = 0
    total: int = 0
    book_total: int = 0
    failed: int = 0
    page: int = 0
    output_path: Path | None = None


ProgressCallback = Callable[[CrawlEvent], None]

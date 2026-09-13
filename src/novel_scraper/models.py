from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Chapter:
    index: int
    title: str
    url: str
    number: int | None = None


@dataclass(frozen=True, slots=True)
class Book:
    title: str
    author: str
    description: str
    source_url: str
    chapters: tuple[Chapter, ...]


@dataclass(frozen=True, slots=True)
class FetchedPage:
    number: int
    url: str
    content: str


@dataclass(frozen=True, slots=True)
class CrawlResult:
    book: Book
    output_path: Path
    chapters_path: Path
    completed: int
    skipped: int
    failed: int
    cancelled: bool = False

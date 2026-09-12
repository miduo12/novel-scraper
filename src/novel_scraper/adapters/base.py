from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from ..models import Book, Chapter, FetchedPage


class SiteAdapter(ABC):
    name = "base"

    def __init__(self, http_client: object) -> None:
        self.http = http_client

    @classmethod
    @abstractmethod
    def matches(cls, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def normalize_book_url(self, url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse_book(self, html: str, source_url: str) -> Book:
        raise NotImplementedError

    @abstractmethod
    def fetch_chapter_pages(
        self,
        chapter: Chapter,
        max_pages: int,
        *,
        on_page: Callable[[int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[FetchedPage, ...]:
        raise NotImplementedError

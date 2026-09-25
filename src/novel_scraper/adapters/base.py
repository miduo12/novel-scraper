from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from ..models import Book, Chapter, FetchedPage
from ..parsers import clean_node_text, make_soup, strip_page_marker


class SiteAdapter(ABC):
    """Base contract and descriptive metadata for a supported novel site."""

    id: str | None = None
    name = "base"
    display_name: str | None = None
    domains: tuple[str, ...] = ()
    example_url = ""

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

    def parse_chapter_title(self, html: str) -> str:
        """Best-effort generic title parser for adapters without a site override."""
        soup = make_soup(html)
        title = clean_node_text(soup.select_one("h1"))
        if not title and soup.title is not None:
            title = clean_node_text(soup.title)
        return strip_page_marker(title)

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

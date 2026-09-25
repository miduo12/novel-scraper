from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urljoin, urlparse

from ..exceptions import ChapterContentError, CrawlCancelled, ParseError
from ..models import Book, Chapter, FetchedPage
from ..parsers import (
    clean_node_text,
    html_fragment_to_text,
    make_soup,
    strip_leading_chapter_heading,
)
from ..utils import parse_chapter_number
from .base import SiteAdapter

_CHAPTER_HREF = re.compile(r"(?:chapter|read|\.html?$|/\d+(?:/|$))", re.IGNORECASE)
_AUTHOR = re.compile(r"(?:\u4f5c\u8005|\u4f5c\u5bb6)\s*[:：]?\s*(.*)")
_SKIP_CONTENT = re.compile(r"(?:list|nav|menu|catalog|\u76ee\u5f55)", re.IGNORECASE)


class GenericAdapter(SiteAdapter):
    """Conservative HTML adapter used only when no site-specific adapter matches."""

    id = "generic"
    name = "generic"
    display_name = "\u666e\u901a\u5c0f\u8bf4\u7f51\u7ad9\uff08\u901a\u7528\u89e3\u6790\uff09"
    domains: tuple[str, ...] = ()
    example_url = ""
    is_fallback = True

    @classmethod
    def matches(cls, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)

    def normalize_book_url(self, url: str) -> str:
        if not self.matches(url):
            raise ParseError(f"\u65e0\u6548\u7684\u7f51\u7ad9 URL\uff1a{url}")
        return url

    def parse_book(self, html: str, source_url: str) -> Book:
        soup = make_soup(html)
        title = clean_node_text(soup.select_one("h1"))
        if not title and soup.title is not None:
            title = clean_node_text(soup.title)
        if not title:
            raise ParseError("\u65e0\u6cd5\u89e3\u6790\u5c0f\u8bf4\u6807\u9898")

        author = self._find_author(soup)
        chapters = self._find_chapters(soup, source_url)
        if not chapters:
            raise ParseError("\u65e0\u6cd5\u627e\u5230\u7ae0\u8282\u5217\u8868")

        description = ""
        description_meta = soup.select_one('meta[name="description"]')
        if description_meta is not None:
            description = str(description_meta.get("content") or "").strip()
        return Book(title, author, description, source_url, chapters)

    @staticmethod
    def _find_author(soup) -> str:
        author_meta = soup.select_one(
            'meta[property="og:novel:author"], meta[name="author"], meta[name="writer"]'
        )
        if author_meta is not None and author_meta.get("content"):
            return str(author_meta["content"]).strip()

        for node in soup.find_all(True):
            attrs = " ".join(
                [str(node.get("id", "")), " ".join(str(x) for x in node.get("class", []))]
            )
            if not re.search(r"author|writer|\u4f5c\u8005|\u4f5c\u5bb6", attrs, re.IGNORECASE):
                continue
            text = clean_node_text(node)
            match = _AUTHOR.search(text)
            value = match.group(1).strip() if match else text
            value = re.sub(r"^(?:\u4f5c\u8005|\u4f5c\u5bb6)\s*[:：]?\s*", "", value).strip()
            if value:
                return value
        return ""

    @staticmethod
    def _find_chapters(soup, source_url: str) -> tuple[Chapter, ...]:
        source = urlparse(source_url)
        source_host = (source.hostname or "").lower()
        source_path = source.path.rstrip("/")
        skipped_segments = {"author", "writer", "history", "sort", "search", "category", "login", "register"}
        anchors = []
        for anchor in soup.select("a[href]"):
            href = str(anchor.get("href", "")).strip()
            title = clean_node_text(anchor)
            if not href or not title or href.lower().startswith(("javascript:", "mailto:")):
                continue
            chapter_url = urljoin(source_url, href)
            parsed = urlparse(chapter_url)
            if parsed.scheme not in {"http", "https"}:
                continue
            if (parsed.hostname or "").lower() != source_host:
                continue
            path = parsed.path.rstrip("/")
            if path in {source_path, f"{source_path}.html"}:
                continue
            if skipped_segments.intersection(part.lower().split(".", 1)[0] for part in parsed.path.split("/")):
                continue
            if not _CHAPTER_HREF.search(parsed.path):
                continue
            anchors.append((anchor, title, chapter_url))

        # Prefer the deepest semantic directory/list container. This avoids mixing
        # navigation and recommendations into a site's chapter catalog.
        grouped: dict[int, tuple[object, list[tuple[object, str, str]]]] = {}
        for anchor, title, chapter_url in anchors:
            for parent in anchor.parents:
                attrs = " ".join(
                    [str(parent.get("id", "")), " ".join(str(x) for x in parent.get("class", []))]
                ).lower()
                if any(key in attrs for key in ("chapter", "catalog", "list", "directory", "dir")):
                    entry = grouped.setdefault(id(parent), (parent, []))
                    entry[1].append((anchor, title, chapter_url))

        selected = anchors
        if grouped:
            max_count = max(len(items) for _, items in grouped.values())
            best_groups = [
                (node, items) for node, items in grouped.values()
                if len(items) == max_count
            ]
            node, _items = max(best_groups, key=lambda item: len(list(item[0].parents)))
            selected = [item for item in anchors if node in item[0].parents]

        chapters: list[Chapter] = []
        seen: set[str] = set()
        for _anchor, title, chapter_url in selected:
            if chapter_url in seen:
                continue
            seen.add(chapter_url)
            chapters.append(
                Chapter(len(chapters) + 1, title, chapter_url, parse_chapter_number(title))
            )
        return tuple(chapters)

    def fetch_chapter_pages(
        self,
        chapter: Chapter,
        max_pages: int,
        *,
        on_page: Callable[[int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[FetchedPage, ...]:
        if max_pages < 1:
            raise ValueError("max_pages must be greater than or equal to 1")
        if should_cancel is not None and should_cancel():
            raise CrawlCancelled("\u7528\u6237\u5df2\u505c\u6b62\u6293\u53d6")
        if on_page is not None:
            on_page(1)

        html = self.http.get_text(chapter.url)
        soup = make_soup(html)
        content = self._find_content(soup)
        if content is None:
            raise ChapterContentError(f"\u65e0\u6cd5\u5b9a\u4f4d\u6b63\u6587\u533a\u57df\uff1a{chapter.url}")
        text = strip_leading_chapter_heading(html_fragment_to_text(content.decode_contents()))
        if not text:
            raise ChapterContentError(f"\u6b63\u6587\u533a\u57df\u4e3a\u7a7a\uff1a{chapter.url}")
        return (FetchedPage(1, chapter.url, text),)

    @staticmethod
    def _find_content(soup):
        candidates: list[tuple[int, int, object]] = []
        priorities = ("content", "txt", "read", "chapter")
        for node in soup.find_all(True):
            attrs = " ".join(
                [str(node.get("id", "")), " ".join(str(x) for x in node.get("class", []))]
            ).lower()
            if not attrs or _SKIP_CONTENT.search(attrs):
                continue
            priority = next((i for i, key in enumerate(priorities) if key in attrs), None)
            if priority is None:
                continue
            text = clean_node_text(node)
            if not text:
                continue
            links_text = sum(len(clean_node_text(a)) for a in node.select("a"))
            if links_text > len(text) * 0.5:
                continue
            candidates.append((priority, -len(text), node))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable
from urllib.parse import urlparse, urlunparse

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from ..exceptions import ChapterContentError, CrawlCancelled, ParseError
from ..models import Book, Chapter, FetchedPage
from ..utils import parse_chapter_number
from .base import SiteAdapter


class BqgAdapter(SiteAdapter):
    """Adapter for the Biquge 616 public novel site."""

    id = "bqg"
    name = "bqg"
    display_name = "笔趣阁 616"
    domains = ("bqg616.cc",)
    example_url = "https://www.bqg616.cc/#/book/717/"

    @classmethod
    def matches(cls, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return any(host == domain or host.endswith(f".{domain}") for domain in cls.domains)

    def normalize_book_url(self, url: str) -> str:
        parsed = urlparse(url)
        book_id = self._book_id(url)
        if not book_id:
            raise ParseError(f"无法从笔趣阁 URL 提取书籍 ID：{url}")
        return urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                "/",
                "",
                "",
                f"/book/{book_id}/",
            )
        )

    def parse_book(self, html: str, source_url: str) -> Book:
        del html  # The site is a SPA; book metadata and its directory come from JSON APIs.
        book_id = self._book_id(source_url)
        if not book_id:
            raise ParseError(f"无法从笔趣阁 URL 提取书籍 ID：{source_url}")

        origin = self._origin(source_url)
        book_payload = self.http.get_json(f"{origin}/api/book", params={"id": book_id})
        directory_payload = self.http.get_json(
            f"{origin}/api/booklist",
            params={"id": book_id},
        )
        title = str(book_payload.get("title") or "").strip()
        if not title:
            raise ParseError(f"笔趣阁书籍接口未返回书名：{source_url}")

        names = directory_payload.get("list")
        if not isinstance(names, list):
            raise ParseError(f"笔趣阁目录接口返回格式无效：{source_url}")

        book_url = self.normalize_book_url(source_url)
        chapters = tuple(
            Chapter(
                index=index,
                title=chapter_title,
                url=f"{origin}/#/book/{book_id}/{index}.html",
                number=parse_chapter_number(chapter_title),
            )
            for index, raw_title in enumerate(names, start=1)
            if (chapter_title := str(raw_title).strip())
        )
        if not chapters:
            raise ParseError(f"笔趣阁目录中没有找到章节：{source_url}")

        return Book(
            title=title,
            author=str(book_payload.get("author") or "").strip(),
            description=str(book_payload.get("intro") or "").strip(),
            source_url=book_url,
            chapters=chapters,
        )

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
            raise CrawlCancelled("用户已停止抓取")
        if on_page is not None:
            on_page(1)

        book_id = self._book_id(chapter.url)
        if not book_id:
            raise ParseError(f"无法从笔趣阁章节 URL 提取书籍 ID：{chapter.url}")
        params = {"id": int(book_id), "chapterid": chapter.index}
        token = self._encrypted_token(params)
        payload = self.http.get_json(
            f"{self._origin(chapter.url)}/api/chapter",
            params={"token": token},
            headers={"Referer": chapter.url},
        )
        content = payload.get("txt")
        if not isinstance(content, str) or not content.strip():
            raise ChapterContentError(f"笔趣阁章节接口未返回正文：{chapter.url}")
        return (FetchedPage(number=1, url=chapter.url, content=content.strip()),)

    @staticmethod
    def _encrypted_token(params: dict[str, int]) -> str:
        plaintext = json.dumps(params, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest = hashlib.md5(b"book@token.html", usedforsecurity=False).hexdigest()
        key = digest[16:].encode("ascii")
        iv = digest[:16].encode("ascii")
        encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext, AES.block_size))
        return base64.b64encode(encrypted).decode("ascii")

    @staticmethod
    def _book_id(url: str) -> str:
        parsed = urlparse(url)
        for candidate in (parsed.path, parsed.fragment):
            path = "/" + candidate.lstrip("/#")
            parts = path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "book" and parts[1].isdigit():
                return parts[1]
        return ""

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme or 'https'}://{parsed.netloc}"

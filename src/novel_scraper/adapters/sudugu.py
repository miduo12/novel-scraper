from __future__ import annotations

import logging
import re
from collections.abc import Callable
from urllib.parse import urljoin, urlparse, urlunparse

from ..exceptions import ChapterContentError, CrawlCancelled, ParseError
from ..models import Book, Chapter, FetchedPage
from ..parsers import (
    clean_node_text,
    html_fragment_to_text,
    make_soup,
    strip_leading_chapter_heading,
    strip_page_marker,
)
from ..utils import content_hash, parse_chapter_number
from .base import SiteAdapter

logger = logging.getLogger(__name__)

_PAGE_MARKER = re.compile(r"[（(]\s*(\d+)\s*/\s*(\d+)\s*[）)]")
_CHAPTER_FILE = re.compile(r"^(?P<book_id>\d+)/(?P<chapter_id>\d+)(?:_(?P<page>\d+))?\.html$")


class SuduguAdapter(SiteAdapter):
    """Adapter for www.sudugu.cc."""

    name = "sudugu"
    site_domain = "sudugu.cc"

    @classmethod
    def matches(cls, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host == cls.site_domain or host.endswith(f".{cls.site_domain}")

    def normalize_book_url(self, url: str) -> str:
        parsed = urlparse(url)
        match = re.match(r"^/(?P<book_id>\d+)(?:/[^/]*\.html)?/?$", parsed.path)
        if not match:
            raise ParseError(f"无法从速读谷 URL 推导目录地址：{url}")
        return urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                f"/{match.group('book_id')}/",
                "",
                "",
                "",
            )
        )

    def parse_book(self, html: str, source_url: str) -> Book:
        soup = make_soup(html)
        book_url = self.normalize_book_url(source_url)
        title = ""
        if soup.title is not None:
            title = clean_node_text(soup.title).split("-", 1)[0].strip()
        if not title:
            title = clean_node_text(soup.select_one("h1"))

        author_text = clean_node_text(soup.select_one('a[href*="authorarticle.php"]'))
        author = author_text.split("：", 1)[-1].strip() if author_text else ""
        description = clean_node_text(soup.select_one(".des"))
        chapters = self.parse_chapter_list(html, book_url)

        if not title:
            raise ParseError("未能解析速读谷小说标题")
        if not chapters:
            raise ParseError("速读谷目录中没有找到章节链接")
        return Book(
            title=title,
            author=author,
            description=description,
            source_url=book_url,
            chapters=chapters,
        )

    def parse_chapter_list(self, html: str, book_url: str) -> tuple[Chapter, ...]:
        soup = make_soup(html)
        container = soup.select_one("#list")
        if container is None:
            raise ParseError("未找到速读谷目录容器 #list")

        chapters: list[Chapter] = []
        seen_urls: set[str] = set()
        for anchor in container.select("li a[href]"):
            href = str(anchor.get("href", "")).strip()
            if not href:
                continue
            chapter_url = urljoin(book_url, href)
            if chapter_url in seen_urls:
                continue
            title = clean_node_text(anchor)
            if not title:
                continue
            seen_urls.add(chapter_url)
            chapters.append(
                Chapter(
                    index=len(chapters) + 1,
                    title=title,
                    url=chapter_url,
                    number=parse_chapter_number(title),
                )
            )
        return tuple(chapters)

    def parse_chapter_title(self, html: str) -> str:
        soup = make_soup(html)
        heading = clean_node_text(soup.select_one("h1"))
        if heading:
            heading = heading.split(">")[-1].strip()
        if not heading and soup.title is not None:
            heading = clean_node_text(soup.title).split("-", 1)[0].strip()
        heading = _PAGE_MARKER.sub("", heading).strip()
        return strip_page_marker(heading)

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
        base_url = self._chapter_base_url(chapter.url)

        if should_cancel is not None and should_cancel():
            raise CrawlCancelled("用户已停止抓取")
        if on_page is not None:
            on_page(1)
        first_html = self.http.get_text(base_url, headers={"Referer": chapter.url})
        first_text, _current, total_pages = self._parse_page(first_html, base_url)
        if not first_text:
            raise ChapterContentError(f"速读谷章节正文为空：{base_url}")

        pages: list[FetchedPage] = [FetchedPage(number=1, url=base_url, content=first_text)]
        seen_hashes = {content_hash(first_text)}
        page_count = min(total_pages or max_pages, max_pages)

        for page_number in range(2, page_count + 1):
            if should_cancel is not None and should_cancel():
                raise CrawlCancelled("用户已停止抓取")
            if on_page is not None:
                on_page(page_number)
            page_url = self._page_url(base_url, page_number)
            page_html = self.http.get_text(page_url, headers={"Referer": chapter.url})
            text, _current, _total = self._parse_page(page_html, page_url)
            if not text:
                break
            digest = content_hash(text)
            if digest in seen_hashes:
                logger.info("    page %d 与上一页内容相同，章节结束", page_number)
                break
            seen_hashes.add(digest)
            pages.append(FetchedPage(number=page_number, url=page_url, content=text))

        if total_pages and total_pages > max_pages:
            logger.warning("    章节共 %d 页，达到最大分页数 %d", total_pages, max_pages)
        return tuple(pages)

    def _parse_page(self, html: str, url: str) -> tuple[str, int | None, int | None]:
        soup = make_soup(html)
        heading = clean_node_text(soup.select_one("h1"))
        marker = _PAGE_MARKER.search(heading)
        current = int(marker.group(1)) if marker else None
        total = int(marker.group(2)) if marker else None

        container = soup.select_one(".con")
        if container is None:
            raise ChapterContentError(f"未找到速读谷正文容器 .con：{url}")
        fragment = container.decode_contents()
        text = strip_leading_chapter_heading(html_fragment_to_text(fragment))
        return text, current, total

    @staticmethod
    def _chapter_base_url(url: str) -> str:
        parsed = urlparse(url)
        match = _CHAPTER_FILE.match(parsed.path.lstrip("/"))
        if not match:
            raise ParseError(f"无法解析速读谷章节地址：{url}")
        path = f"/{match.group('book_id')}/{match.group('chapter_id')}.html"
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

    @staticmethod
    def _page_url(base_url: str, page_number: int) -> str:
        if page_number == 1:
            return base_url
        parsed = urlparse(base_url)
        path = re.sub(r"\.html$", f"_{page_number}.html", parsed.path)
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

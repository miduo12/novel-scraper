from __future__ import annotations

import logging
import re
from collections.abc import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from ..exceptions import ChapterContentError, CrawlCancelled, FetchError, ParseError
from ..models import Book, Chapter, FetchedPage
from ..parsers import (
    clean_node_text,
    html_fragment_to_text,
    make_soup,
    strip_leading_chapter_heading,
    strip_page_marker,
)
from ..utils import make_page_url
from .base import SiteAdapter

logger = logging.getLogger(__name__)


class DeqixsAdapter(SiteAdapter):
    """Adapter for www.deqixs.cc."""

    name = "deqixs"
    site_domain = "deqixs.cc"
    ajax_path = "/modules/article/ajax2.php"

    @classmethod
    def matches(cls, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host == cls.site_domain or host.endswith(f".{cls.site_domain}")

    def normalize_book_url(self, url: str) -> str:
        parsed = urlparse(url)
        match = re.match(r"^(/books/\d+/)(?:[^/]*\.html)?$", parsed.path)
        if not match:
            raise ParseError(f"无法从小说的章节 URL 推导目录地址：{url}")
        return urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                match.group(1),
                "",
                "",
                "",
            )
        )

    def parse_book(self, html: str, source_url: str) -> Book:
        soup = make_soup(html)
        book_url = self.normalize_book_url(source_url)

        title = clean_node_text(soup.select_one("h1.booktitle"))
        if not title:
            meta_title = soup.find("meta", attrs={"property": "og:novel:book_name"})
            if meta_title is not None and meta_title.get("content"):
                title = str(meta_title["content"]).strip()
        if not title and soup.title is not None:
            title = clean_node_text(soup.title).split("_", 1)[0].strip()

        author_meta = soup.find("meta", attrs={"property": "og:novel:author"})
        author = ""
        if author_meta is not None and author_meta.get("content"):
            author = str(author_meta["content"]).strip()
        if not author:
            author = clean_node_text(soup.select_one("a[href^='/author/']"))

        description_meta = soup.find("meta", attrs={"property": "og:description"})
        description = ""
        if description_meta is not None and description_meta.get("content"):
            description = " ".join(str(description_meta["content"]).split())
        if not description:
            description = clean_node_text(soup.select_one(".bookintro"))

        chapters = self.parse_chapter_list(html, book_url)
        if not title:
            raise ParseError("未能解析小说标题")
        if not chapters:
            raise ParseError("目录中没有找到章节链接")

        return Book(
            title=title,
            author=author,
            description=description,
            source_url=book_url,
            chapters=chapters,
        )

    def parse_chapter_list(self, html: str, book_url: str) -> tuple[Chapter, ...]:
        soup = make_soup(html)
        container = soup.select_one("#list-chapterAll")
        if container is None:
            raise ParseError("未找到完整章节容器 #list-chapterAll")

        chapters: list[Chapter] = []
        seen_urls: set[str] = set()
        for anchor in container.select("dd a[href]"):
            href = str(anchor.get("href", "")).strip()
            if not href or href.lower().startswith("javascript:"):
                continue
            chapter_url = urljoin(book_url, href)
            parsed = urlparse(chapter_url)
            if not parsed.path.lower().endswith(".html") or chapter_url in seen_urls:
                continue
            title = clean_node_text(anchor)
            if not title:
                continue
            seen_urls.add(chapter_url)
            chapters.append(Chapter(index=len(chapters) + 1, title=title, url=chapter_url))

        return tuple(chapters)

    def parse_chapter_title(self, html: str) -> str:
        soup = make_soup(html)
        title = clean_node_text(soup.select_one("h1.pt10"))
        if not title:
            meta_title = soup.find("meta", attrs={"property": "og:title"})
            if meta_title is not None and meta_title.get("content"):
                title = str(meta_title["content"]).split("_", 1)[-1]
        return strip_page_marker(title)

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

        page_url = make_page_url(chapter.url, 1)
        logger.info("    请求整章正文")

        # The current Deqixs ajax2 endpoint returns the complete chapter in one
        # response. Avoid fetching the HTML shell and a duplicate ?page=2.
        try:
            fragment = self._fetch_ajax_content(None, page_url)
        except ChapterContentError:
            # Fallback for a future/site variant that embeds the text in HTML.
            page_html = self.http.get_text(page_url, headers={"Referer": chapter.url})
            fragment = self._embedded_content(page_html)
            if not fragment:
                fragment = self._fetch_ajax_content(page_html, page_url)

        text = strip_leading_chapter_heading(html_fragment_to_text(fragment))
        if not text:
            raise ChapterContentError(f"章节正文为空：{page_url}")

        return (FetchedPage(number=1, url=page_url, content=text),)

    def _embedded_content(self, html: str) -> str:
        soup = make_soup(html)
        container = soup.select_one("#chapter-content")
        if container is None:
            return ""
        fragment = "".join(str(child) for child in container.contents)
        return fragment if html_fragment_to_text(fragment) else ""

    def _fetch_ajax_content(self, page_html: str | None, page_url: str) -> str:
        canonical_url = make_page_url(page_url, 1)
        script_url = self._script_url(canonical_url)
        if not script_url:
            if page_html is None:
                raise ChapterContentError(f"无法构造章节签名地址：{page_url}")
            soup = make_soup(page_html)
            script = soup.select_one('script[src*="chapter.js.php"]')
            if script is None or not script.get("src"):
                raise ChapterContentError(f"章节页没有正文容器或签名脚本：{page_url}")
            script_url = urljoin(canonical_url, str(script["src"]))

        script_url = self._replace_query_value(script_url, "referrer", canonical_url)
        script_headers = {
            "Accept": "*/*",
            "Referer": canonical_url,
            "Origin": self._origin(canonical_url),
        }
        script_text = self.http.get_text(script_url, headers=script_headers)

        token = self._js_string(script_text, "chapterToken")
        timestamp = self._js_number(script_text, "timestamp")
        nonce = self._js_string(script_text, "nonce")
        if not token or not timestamp or not nonce:
            raise ChapterContentError(f"章节签名参数不完整：{page_url}")

        ajax_url = urljoin(page_url, self.ajax_path)
        payload = self.http.get_json(
            ajax_url,
            params={
                "aid": self._query_value(script_url, "aid"),
                "cid": self._query_value(script_url, "cid"),
                "token": token,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": canonical_url,
                "Origin": self._origin(canonical_url),
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        if payload.get("status") != 1:
            message = payload.get("message") or "未知错误"
            raise FetchError(f"正文接口返回失败：{message}")

        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("content"):
            raise ChapterContentError(f"正文接口没有返回内容：{page_url}")
        return str(data["content"])

    @staticmethod
    def _script_url(chapter_url: str) -> str:
        parsed = urlparse(chapter_url)
        match = re.match(r"^/books/(?P<aid>\d+)/(?P<cid>\d+)\.html$", parsed.path)
        if not match:
            return ""
        query = urlencode(
            {
                "aid": match.group("aid"),
                "cid": match.group("cid"),
                "referrer": chapter_url,
            }
        )
        return urlunparse(
            (parsed.scheme, parsed.netloc, "/scripts/chapter.js.php", "", query, "")
        )

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _query_value(url: str, key: str) -> str:
        values = parse_qs(urlparse(url).query).get(key)
        if not values:
            raise ParseError(f"签名脚本缺少参数 {key}: {url}")
        return values[0]

    @staticmethod
    def _replace_query_value(url: str, key: str, value: str) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query[key] = [value]
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params,
             urlencode(query, doseq=True), parsed.fragment)
        )

    @staticmethod
    def _js_string(source: str, name: str) -> str:
        match = re.search(rf"\b{re.escape(name)}\s*=\s*(['\"])(.*?)\1", source)
        return match.group(2) if match else ""

    @staticmethod
    def _js_number(source: str, name: str) -> str:
        match = re.search(rf"\b{re.escape(name)}\s*=\s*(\d+)", source)
        return match.group(1) if match else ""

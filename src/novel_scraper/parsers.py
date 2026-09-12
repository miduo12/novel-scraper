from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup, Tag

from .exceptions import ParseError

_CHAPTER_HEADING_RE = re.compile(
    r"^第\s*[0-9零〇一二三四五六七八九十百千万两]{1,20}\s*章(?:\s|$)"
)


def make_soup(markup: str) -> BeautifulSoup:
    return BeautifulSoup(markup, "html.parser")


def clean_node_text(node: Tag | None) -> str:
    if node is None:
        return ""
    text = node.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def html_fragment_to_text(fragment: str) -> str:
    """Extract readable text from a chapter HTML fragment."""
    if not fragment or not fragment.strip():
        return ""

    soup = BeautifulSoup(fragment, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")

    for block in soup.find_all(["p", "div", "section", "article", "li", "h1", "h2", "h3"]):
        block.append("\n")

    raw = html.unescape(soup.get_text())
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    raw = raw.replace("\u3000", " ")

    lines: list[str] = []
    for raw_line in raw.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", raw_line).strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        lines.append(line)

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines).strip()


def strip_leading_chapter_heading(text: str) -> str:
    """Remove a duplicated chapter title at the beginning of API content."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if len(line) <= 120 and _CHAPTER_HEADING_RE.match(line.strip()):
            del lines[index]
        break

    while lines and not lines[0].strip():
        lines.pop(0)

    return "\n".join(lines).strip()


def strip_page_marker(title: str) -> str:
    title = re.sub(r"\s*\(第\s*\d*\s*/\s*\d*\s*页\)\s*$", "", title)
    return re.sub(r"\s+", " ", title).strip()


def require_text(value: str, message: str) -> str:
    if not value.strip():
        raise ParseError(message)
    return value.strip()

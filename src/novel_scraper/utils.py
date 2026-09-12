from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def make_page_url(base_url: str, page: int) -> str:
    """Return a chapter page URL without adding ?page=1."""
    if page < 1:
        raise ValueError("page must be greater than or equal to 1")

    parsed = urlparse(base_url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    if page == 1:
        query.pop("page", None)
    else:
        query["page"] = [str(page)]

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query, doseq=True),
            parsed.fragment,
        )
    )


def content_hash(text: str) -> str:
    """Hash normalized text so whitespace differences are ignored."""
    normalized = "".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def safe_filename(value: str, fallback: str = "untitled", max_length: int = 80) -> str:
    """Convert an arbitrary title into a Windows-safe file name."""
    value = _INVALID_FILENAME_CHARS.sub("_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = fallback
    if value.upper() in _WINDOWS_RESERVED_NAMES:
        value = f"_{value}"
    return value[:max_length].rstrip(" .") or fallback


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text atomically enough for checkpoint-style files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text, encoding=encoding, newline="\n")
    try:
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def safe_atomic_write_text(
    path: Path,
    text: str,
    encoding: str = "utf-8",
) -> Path:
    """Write to the requested file, or a new sibling if it is locked."""
    try:
        atomic_write_text(path, text, encoding)
        return path
    except PermissionError:
        from datetime import datetime

        timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        alternate = path.with_name(f"{path.stem}_new_{timestamp}{path.suffix}")
        atomic_write_text(alternate, text, encoding)
        return alternate


_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}
_CHAPTER_NUMBER_RE = re.compile(r"^第\s*([0-9零〇一二三四五六七八九十百千万两亿]+)\s*章")


def chinese_number_to_int(value: str) -> int:
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[char]
            continue
        unit = _CHINESE_UNITS.get(char)
        if unit is None:
            continue
        if unit < 10000:
            section += (number or 1) * unit
        else:
            section += number
            total += section * unit
            section = 0
        number = 0
    return total + section + number


def parse_chapter_number(title: str) -> int | None:
    match = _CHAPTER_NUMBER_RE.match(title.strip())
    if match is None:
        return None
    raw = match.group(1)
    if raw.isdigit():
        return int(raw)
    try:
        return chinese_number_to_int(raw)
    except (KeyError, ValueError):
        return None

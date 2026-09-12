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


def atomic_write_text(path: Path, text: str) -> None:
    """Write UTF-8 text atomically enough for checkpoint-style files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8", newline="\n")
    temp_path.replace(path)

from pathlib import Path

from novel_scraper import utils as utils_module
from novel_scraper.utils import (
    atomic_write_text,
    content_hash,
    make_page_url,
    parse_chapter_number,
    safe_atomic_write_text,
    safe_filename,
)


def test_make_page_url_removes_page_one() -> None:
    base = "https://www.deqixs.cc/books/99/63332.html"
    assert make_page_url(base, 1) == base


def test_make_page_url_adds_later_pages() -> None:
    base = "https://www.deqixs.cc/books/99/63332.html"
    assert make_page_url(base, 3) == f"{base}?page=3"


def test_make_page_url_preserves_other_query_params() -> None:
    base = "https://example.com/book/chapter.html?from=test&page=2"
    assert make_page_url(base, 1) == "https://example.com/book/chapter.html?from=test"
    assert make_page_url(base, 2) == "https://example.com/book/chapter.html?from=test&page=2"


def test_content_hash_ignores_whitespace() -> None:
    assert content_hash("第一段 第二段") == content_hash("第一段\n\n第二段")


def test_safe_filename() -> None:
    assert safe_filename("第1章：开始/测试?") == "第1章：开始_测试_"


def test_atomic_write_text(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "file.txt"
    atomic_write_text(target, "内容")
    assert target.read_text(encoding="utf-8") == "内容"


def test_parse_chapter_number() -> None:
    assert parse_chapter_number("第1156章 标题") == 1156
    assert parse_chapter_number("第一千五百八十九章 标题") == 1589
    assert parse_chapter_number("没有章号") is None


def test_safe_atomic_write_uses_alternate_when_target_locked(tmp_path, monkeypatch) -> None:
    target = tmp_path / "clean_report.csv"
    target.write_text("old", encoding="utf-8")
    real_write = utils_module.atomic_write_text

    def fake_write(path, text, encoding="utf-8"):
        if path == target:
            raise PermissionError("locked")
        return real_write(path, text, encoding)

    monkeypatch.setattr(utils_module, "atomic_write_text", fake_write)
    actual = safe_atomic_write_text(target, "new")

    assert actual != target
    assert actual.read_text(encoding="utf-8") == "new"
    assert target.read_text(encoding="utf-8") == "old"

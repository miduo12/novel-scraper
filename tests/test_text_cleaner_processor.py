import json
from pathlib import Path

from novel_scraper.text_cleaner.models import CleaningMode
from novel_scraper.text_cleaner.blacklist import AdBlacklistStore
from novel_scraper.text_cleaner.processor import BookCleaner


def make_book(tmp_path: Path) -> Path:
    book_dir = tmp_path / "测试小说"
    chapter_dir = book_dir / "chapters"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / "0001_第1章.txt").write_text(
        "这是正常的。\n\n"
        "「但———-可惜了，身为穷人的他，注定会成为我们的狗。\\\"\n\n"
        "這是什么？\n\n"
        "本章由测试小说网提供，请记住本站网址。\n\n"
        "1\n\n"
        "\\\"",
        encoding="utf-8",
    )
    (chapter_dir / "0002_第2章.txt").write_text(
        "这是正常的。\n\n他打开微信，网站页面显示正常。\n\n你好,他说。",
        encoding="utf-8",
    )
    return book_dir

def test_detect_mode_keeps_original_and_writes_reports(tmp_path: Path) -> None:
    book_dir = make_book(tmp_path)
    original = (book_dir / "chapters" / "0001_第1章.txt").read_text(encoding="utf-8")

    result = BookCleaner(
        blacklist_store=AdBlacklistStore(tmp_path / "blacklist.json")
    ).process(book_dir, CleaningMode.DETECT)

    assert result.chapter_count == 2
    assert not (book_dir / "cleaned").exists()
    assert (book_dir / "chapters" / "0001_第1章.txt").read_text(encoding="utf-8") == original
    assert (book_dir / "reports" / "clean_report.json").exists()
    assert (book_dir / "reports" / "clean_report.csv").exists()
    assert (book_dir / "reports" / "clean_log.json").exists()


def test_auto_mode_outputs_cleaned_files_and_preserves_original(tmp_path: Path) -> None:
    book_dir = make_book(tmp_path)
    original = (book_dir / "chapters" / "0001_第1章.txt").read_text(encoding="utf-8")

    result = BookCleaner(
        blacklist_store=AdBlacklistStore(tmp_path / "blacklist.json")
    ).process(book_dir, CleaningMode.AUTO)

    assert (book_dir / "chapters" / "0001_第1章.txt").read_text(encoding="utf-8") == original
    assert result.cleaned_book_path is not None
    assert result.cleaned_book_path.exists()
    cleaned = (book_dir / "cleaned" / "chapters" / "0001_第1章.txt").read_text(encoding="utf-8")
    assert "本章由测试小说网提供" not in cleaned
    assert "這是什么" not in cleaned
    assert "这是什么" in cleaned
    assert "———-" not in cleaned
    assert "「但——可惜了，身为穷人的他，注定会成为我们的狗。」" in cleaned
    assert "\n1\n" not in cleaned
    assert '\\"' not in cleaned
    normal = (book_dir / "cleaned" / "chapters" / "0002_第2章.txt").read_text(encoding="utf-8")
    assert "他打开微信，网站页面显示正常。" in normal
    assert "你好，他说。" in normal
    report = json.loads((book_dir / "reports" / "clean_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["applied_count"] >= 6

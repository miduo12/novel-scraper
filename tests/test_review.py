import json
from pathlib import Path

from novel_scraper.text_cleaner.models import (
    BookCleanResult,
    ChapterCleanResult,
    CleaningMode,
    Confidence,
    TextIssue,
)
from novel_scraper.text_cleaner.review import (
    apply_review_decisions,
    build_diff_changes,
    write_reviewed_output,
)


def make_chapter(path: Path) -> ChapterCleanResult:
    original = "第一句。\n\n他说道.\n\n1"
    cleaned = "第一句。\n\n他说道。"
    issues = [
        TextIssue(
            chapter="第1章",
            category="punctuation",
            confidence=Confidence.HIGH,
            confidence_score=0.95,
            rule="ascii_period_in_chinese",
            reason="中文语境中的英文句号明显不匹配",
            original=".",
            replacement="。",
            action="replace",
            applied=True,
        ),
        TextIssue(
            chapter="第1章",
            category="web_residue",
            confidence=Confidence.HIGH,
            confidence_score=0.95,
            rule="standalone_page_number",
            reason="疑似网页页码残留",
            original="1",
            replacement="",
            action="remove",
            applied=True,
        ),
    ]
    return ChapterCleanResult("第1章", path, original, cleaned, issues)


def test_review_can_reject_selected_change() -> None:
    chapter = make_chapter(Path("0001_第1章.txt"))
    changes = build_diff_changes(chapter)
    punctuation = next(change for change in changes if change.category == "punctuation")

    reviewed = apply_review_decisions(
        chapter.original_text,
        changes,
        {change.index: change.index != punctuation.index for change in changes},
    )

    assert "他说道." in reviewed
    assert "\n1" not in reviewed


def test_write_reviewed_output_preserves_original_and_writes_decisions(tmp_path: Path) -> None:
    chapter = make_chapter(tmp_path / "0001_第1章.txt")
    result = BookCleanResult(
        book_dir=tmp_path,
        mode=CleaningMode.AUTO,
        chapter_count=1,
        chapters=[chapter],
        output_dir=tmp_path / "cleaned",
        reports_dir=tmp_path / "reports",
    )
    changes = build_diff_changes(chapter)
    punctuation = next(change for change in changes if change.category == "punctuation")
    decisions = {
        "第1章": {
            change.index: change.index != punctuation.index
            for change in changes
        }
    }

    paths = write_reviewed_output(result, decisions)

    assert "他说道." in paths["combined"].read_text(encoding="utf-8")
    assert paths["decisions"].exists()
    payload = json.loads(paths["decisions"].read_text(encoding="utf-8"))
    punctuation_payload = next(
        item for item in payload["chapters"][0]["changes"] if item["category"] == "punctuation"
    )
    assert punctuation_payload["accepted"] is False


def test_detect_mode_suggestions_can_be_reviewed_and_applied(tmp_path: Path) -> None:
    issue = TextIssue(
        chapter="第1章",
        category="punctuation",
        confidence=Confidence.HIGH,
        confidence_score=0.95,
        rule="ascii_period_in_chinese",
        reason="中文语境中的英文句号明显不匹配",
        original=".",
        replacement="。",
        action="report",
        applied=False,
    )
    chapter = ChapterCleanResult(
        title="第1章",
        source_path=tmp_path / "0001_第1章.txt",
        original_text="他说道.",
        cleaned_text="他说道.",
        issues=[issue],
    )
    result = BookCleanResult(
        book_dir=tmp_path,
        mode=CleaningMode.DETECT,
        chapter_count=1,
        chapters=[chapter],
        issue_counts={"punctuation": 1},
    )
    changes = build_diff_changes(chapter)
    assert len(changes) == 1
    assert changes[0].category == "punctuation"
    paths = write_reviewed_output(result, {"第1章": {0: True}})
    assert "他说道。" in paths["combined"].read_text(encoding="utf-8")

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..utils import safe_atomic_write_text, safe_filename
from .cleaner import split_paragraphs
from .models import BookCleanResult, ChapterCleanResult, Confidence, TextIssue


@dataclass(slots=True)
class DiffChange:
    index: int
    tag: str
    i1: int
    i2: int
    j1: int
    j2: int
    original: str
    replacement: str
    category: str = "text_change"
    rule: str = "cleaned_text_diff"
    reason: str = "保守清洗产生的文本修改"
    confidence: str = Confidence.HIGH.value

    def to_dict(self, accepted: bool = True) -> dict[str, object]:
        return {
            "index": self.index,
            "tag": self.tag,
            "original": self.original,
            "replacement": self.replacement,
            "category": self.category,
            "rule": self.rule,
            "reason": self.reason,
            "confidence": self.confidence,
            "accepted": accepted,
        }


def build_review_target(chapter: ChapterCleanResult) -> str:
    if chapter.cleaned_text != chapter.original_text:
        return chapter.cleaned_text

    proposed = chapter.original_text
    for issue in chapter.issues:
        if issue.confidence == Confidence.LOW:
            continue
        if not issue.original or issue.original == issue.replacement:
            continue
        if issue.original in proposed:
            proposed = proposed.replace(issue.original, issue.replacement, 1)
    return proposed


def build_diff_changes(chapter: ChapterCleanResult) -> list[DiffChange]:
    target_text = build_review_target(chapter)
    if chapter.original_text == target_text:
        return []

    original_paragraphs = split_paragraphs(chapter.original_text)
    target_paragraphs = split_paragraphs(target_text)
    original_spans = _paragraph_spans(chapter.original_text, original_paragraphs)
    target_spans = _paragraph_spans(target_text, target_paragraphs)
    matcher = difflib.SequenceMatcher(
        None,
        original_paragraphs,
        target_paragraphs,
        autojunk=False,
    )
    changes: list[DiffChange] = []

    def add_change(
        original: str,
        replacement: str,
        i1: int,
        i2: int,
        j1: int,
        j2: int,
        tag: str,
    ) -> None:
        if original == replacement or (not original and not replacement):
            return
        issue = _matching_issue(original, replacement, chapter.issues)
        changes.append(
            DiffChange(
                index=len(changes),
                tag=tag,
                i1=i1,
                i2=i2,
                j1=j1,
                j2=j2,
                original=original,
                replacement=replacement,
                category=issue.category if issue else "text_change",
                rule=issue.rule if issue else "cleaned_text_diff",
                reason=issue.reason if issue else "保守清洗产生的文本修改",
                confidence=issue.confidence.value if issue else Confidence.HIGH.value,
            )
        )

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        original_block = original_paragraphs[i1:i2]
        target_block = target_paragraphs[j1:j2]
        paired = min(len(original_block), len(target_block))

        for offset in range(paired):
            oi = i1 + offset
            tj = j1 + offset
            o_start, o_end = original_spans[oi]
            t_start, t_end = target_spans[tj]
            add_change(
                chapter.original_text[o_start:o_end],
                target_text[t_start:t_end],
                o_start,
                o_end,
                t_start,
                t_end,
                "replace",
            )

        for oi in range(i1 + paired, i2):
            o_start, o_end = original_spans[oi]
            insert_at = target_spans[j2][0] if j2 < len(target_spans) else len(target_text)
            add_change(
                chapter.original_text[o_start:o_end],
                "",
                o_start,
                o_end,
                insert_at,
                insert_at,
                "delete",
            )

        for tj in range(j1 + paired, j2):
            t_start, t_end = target_spans[tj]
            insert_at = (
                original_spans[i2][0] if i2 < len(original_spans) else len(chapter.original_text)
            )
            add_change(
                "",
                target_text[t_start:t_end],
                insert_at,
                insert_at,
                t_start,
                t_end,
                "insert",
            )

    return changes


def _paragraph_spans(text: str, paragraphs: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for paragraph in paragraphs:
        start = text.find(paragraph, cursor)
        if start < 0:
            start = cursor
        end = start + len(paragraph)
        spans.append((start, end))
        cursor = end
    return spans


def _matching_issue(
    original: str,
    replacement: str,
    issues: list[TextIssue],
) -> TextIssue | None:
    original_stripped = original.strip()
    fallback: TextIssue | None = None
    for issue in issues:
        issue_original = issue.original.strip()
        issue_replacement = issue.replacement.strip()
        if issue_original and (issue_original in original or original_stripped in issue_original):
            if issue.applied:
                return issue
            fallback = fallback or issue
        if issue_replacement and issue_replacement in replacement:
            if issue.applied:
                return issue
            fallback = fallback or issue
    return fallback


def apply_review_decisions(
    original_text: str,
    changes: list[DiffChange],
    accepted: dict[int, bool],
) -> str:
    accepted_indexes = {index for index, value in accepted.items() if value}
    result: list[str] = []
    last = 0
    for change in changes:
        result.append(original_text[last : change.i1])
        if change.index in accepted_indexes:
            result.append(change.replacement)
        else:
            result.append(change.original)
        last = change.i2
    result.append(original_text[last:])
    reviewed = "".join(result)
    if reviewed != original_text:
        reviewed = re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", reviewed).strip()
    return reviewed


def write_reviewed_output(
    result: BookCleanResult,
    decisions: dict[str, dict[int, bool]],
) -> dict[str, Path]:
    if result.output_dir is None:
        result.output_dir = result.book_dir / "cleaned"
    if result.reports_dir is None:
        result.reports_dir = result.book_dir / "reports"

    chapter_dir = result.output_dir / "chapters"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    snapshots: dict[str, list[DiffChange]] = {}

    for chapter in result.chapters:
        changes = build_diff_changes(chapter)
        snapshots[chapter.title] = changes
        accepted = decisions.get(chapter.title, {change.index: True for change in changes})
        chapter.cleaned_text = apply_review_decisions(
            chapter.original_text,
            changes,
            accepted,
        )
        path = chapter_dir / chapter.source_path.name
        paths[chapter.source_path.name] = safe_atomic_write_text(
            path,
            chapter.cleaned_text.strip() + "\n",
        )

    paths["combined"] = _write_cleaned_book(result)
    decisions_path = result.reports_dir / "review_decisions.json"
    _write_decisions(result, snapshots, decisions, decisions_path)
    paths["decisions"] = decisions_path
    return paths


def _write_cleaned_book(result: BookCleanResult) -> Path:
    assert result.output_dir is not None
    lines = [
        f"{result.book_dir.name}（人工审核后清洗版）",
        f"来源目录：{result.book_dir}",
        "",
    ]
    for chapter in result.chapters:
        lines.extend([chapter.title, "", chapter.cleaned_text.strip(), ""])
    path = result.output_dir / f"{safe_filename(result.book_dir.name, fallback='novel')}_清洗版.txt"
    return safe_atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _write_decisions(
    result: BookCleanResult,
    snapshots: dict[str, list[DiffChange]],
    decisions: dict[str, dict[int, bool]],
    path: Path,
) -> None:
    chapters = []
    for chapter in result.chapters:
        changes = snapshots.get(chapter.title, [])
        accepted = decisions.get(chapter.title, {change.index: True for change in changes})
        chapters.append(
            {
                "chapter": chapter.title,
                "changes": [
                    change.to_dict(accepted=bool(accepted.get(change.index, True)))
                    for change in changes
                ],
            }
        )
    payload = {
        "book_dir": str(result.book_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chapters": chapters,
    }
    safe_atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CleaningMode(str, Enum):
    DETECT = "detect"
    AUTO = "auto"


@dataclass(slots=True)
class TextIssue:
    chapter: str
    category: str
    confidence: Confidence
    confidence_score: float
    rule: str
    reason: str
    original: str
    replacement: str
    action: str = "report"
    applied: bool = False
    paragraph: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "chapter": self.chapter,
            "category": self.category,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "rule": self.rule,
            "reason": self.reason,
            "original": self.original,
            "replacement": self.replacement,
            "action": self.action,
            "applied": self.applied,
            "paragraph": self.paragraph,
        }


@dataclass(slots=True)
class ChapterCleanResult:
    title: str
    source_path: Path
    original_text: str
    cleaned_text: str
    issues: list[TextIssue] = field(default_factory=list)

    @property
    def applied_count(self) -> int:
        return sum(1 for issue in self.issues if issue.applied)


@dataclass(slots=True)
class CleanProgress:
    current: int
    total: int
    chapter: str
    message: str = ""


@dataclass(slots=True)
class BookCleanResult:
    book_dir: Path
    mode: CleaningMode
    chapter_count: int
    chapters: list[ChapterCleanResult]
    output_dir: Path | None = None
    reports_dir: Path | None = None
    cleaned_book_path: Path | None = None
    issue_counts: dict[str, int] = field(default_factory=dict)
    applied_count: int = 0

    @property
    def total_issues(self) -> int:
        return sum(self.issue_counts.values())

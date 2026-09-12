from __future__ import annotations

import re

from .ads import detect_ad
from .blacklist import AdBlacklistEntry
from .models import (
    ChapterCleanResult,
    CleaningMode,
    Confidence,
    TextIssue,
)
from .punctuation import clean_paragraph as clean_punctuation
from .punctuation import detect_web_residue
from .rules import CleanerRules
from .typo import TextStyleProfile, find_issues as find_typo_issues

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


def split_paragraphs(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return _PARAGRAPH_SPLIT.split(stripped)


class ChapterCleaner:
    def __init__(
        self,
        rules: CleanerRules,
        blacklist_entries: list[AdBlacklistEntry] | None = None,
    ) -> None:
        self.rules = rules
        self.blacklist_entries = blacklist_entries or []

    def clean_chapter(
        self,
        title: str,
        source_path: object,
        text: str,
        mode: CleaningMode,
        profile: TextStyleProfile,
    ) -> ChapterCleanResult:
        paragraphs = split_paragraphs(text)
        issues: list[TextIssue] = []
        changed = False

        for index, paragraph in enumerate(paragraphs):
            residue_issue = detect_web_residue(
                paragraph,
                title,
                index,
                len(paragraphs),
            )
            if residue_issue is not None:
                if self._should_apply(residue_issue, mode):
                    residue_issue.applied = True
                    residue_issue.action = "remove"
                    paragraphs[index] = ""
                    changed = True
                    issues.append(residue_issue)
                    continue
                residue_issue.action = "report"
                issues.append(residue_issue)

            ad_issue = detect_ad(
                paragraph,
                title,
                self.rules,
                index,
                self.blacklist_entries,
            )
            if ad_issue is not None:
                if self._should_apply(ad_issue, mode):
                    ad_issue.applied = True
                    ad_issue.action = "delete"
                    paragraphs[index] = ""
                    changed = True
                else:
                    ad_issue.action = "report"
                issues.append(ad_issue)
                if ad_issue.applied:
                    continue

            punctuation_text, punctuation_issues = clean_punctuation(
                paragraphs[index],
                title,
                index,
            )
            for issue in punctuation_issues:
                if self._should_apply(issue, mode):
                    issue.applied = True
                else:
                    issue.action = "report"
                issues.append(issue)

            typo_issues = find_typo_issues(
                punctuation_text,
                title,
                index,
                profile,
                self.rules,
            )
            typo_text = punctuation_text
            for issue in typo_issues:
                if self._should_apply(issue, mode):
                    if issue.original in typo_text:
                        typo_text = typo_text.replace(issue.original, issue.replacement, 1)
                        issue.applied = True
                    else:
                        issue.action = "report"
                else:
                    issue.action = "report"
                issues.append(issue)

            if mode == CleaningMode.AUTO and (punctuation_text != paragraphs[index] or typo_text != punctuation_text):
                paragraphs[index] = typo_text
                changed = True

        cleaned_text = "\n\n".join(part for part in paragraphs if part).strip()
        if mode == CleaningMode.DETECT or not changed:
            cleaned_text = text

        return ChapterCleanResult(
            title=title,
            source_path=source_path,
            original_text=text,
            cleaned_text=cleaned_text,
            issues=issues,
        )

    @staticmethod
    def _should_apply(issue: TextIssue, mode: CleaningMode) -> bool:
        return (
            mode == CleaningMode.AUTO
            and issue.confidence == Confidence.HIGH
            and issue.action in {"delete", "remove", "replace"}
        )

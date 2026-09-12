from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .models import Confidence, TextIssue
from .rules import CleanerRules

_GARBLED_CHARS = {"\ufffd"}
_ZERO_WIDTH_CHARS = {"\u200b", "\u200c", "\u200d", "\ufeff"}


@dataclass(slots=True)
class TextStyleProfile:
    simplified_counts: Counter[str]
    traditional_counts: Counter[str]
    bigrams: Counter[str]
    cjk_total: int

    @classmethod
    def build(cls, texts: list[str], traditional_map: dict[str, str]) -> "TextStyleProfile":
        simplified_counts: Counter[str] = Counter()
        traditional_counts: Counter[str] = Counter()
        bigrams: Counter[str] = Counter()
        cjk_total = 0
        simplified_values = set(traditional_map.values())

        for text in texts:
            cjk_chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
            cjk_total += len(cjk_chars)
            simplified_counts.update(char for char in cjk_chars if char in simplified_values)
            traditional_counts.update(char for char in cjk_chars if char in traditional_map)
            for left, right in zip(cjk_chars, cjk_chars[1:]):
                bigrams[left + right] += 1

        return cls(simplified_counts, traditional_counts, bigrams, cjk_total)

    @property
    def simplified_ratio(self) -> float:
        if self.cjk_total == 0:
            return 0.0
        traditional = sum(self.traditional_counts.values())
        return max(0.0, 1.0 - traditional / self.cjk_total)


def find_issues(
    paragraph: str,
    chapter: str,
    paragraph_index: int,
    profile: TextStyleProfile,
    rules: CleanerRules,
) -> list[TextIssue]:
    issues: list[TextIssue] = []

    for char in paragraph:
        if char in _GARBLED_CHARS:
            issues.append(
                TextIssue(
                    chapter=chapter,
                    category="abnormal_character",
                    confidence=Confidence.HIGH,
                    confidence_score=0.99,
                    rule="replacement_character",
                    reason="出现 Unicode 替换字符，说明抓取或编码过程损坏",
                    original=char,
                    replacement="",
                    action="remove",
                    paragraph=paragraph_index,
                )
            )
        elif char in _ZERO_WIDTH_CHARS or (
            ord(char) < 32 and char not in {"\n", "\r", "\t"}
        ):
            issues.append(
                TextIssue(
                    chapter=chapter,
                    category="abnormal_character",
                    confidence=Confidence.HIGH,
                    confidence_score=0.98,
                    rule="control_or_zero_width_character",
                    reason="出现零宽或控制字符，不属于正文排版",
                    original=char,
                    replacement="",
                    action="remove",
                    paragraph=paragraph_index,
                )
            )

    for index, char in enumerate(paragraph):
        simplified = rules.traditional_map.get(char)
        if simplified is None:
            continue
        same_char_count = paragraph.count(char)
        if same_char_count > 1:
            confidence = Confidence.MEDIUM
            score = 0.58
            reason = "同一段落多次出现该繁体字，可能是作者或专有名词用法，保留原文"
        else:
            left = paragraph[index - 1] if index > 0 else ""
            right = paragraph[index + 1] if index + 1 < len(paragraph) else ""
            local_evidence = 0
            if left and profile.bigrams.get(left + simplified, 0) > 0:
                local_evidence += 1
            if right and profile.bigrams.get(simplified + right, 0) > 0:
                local_evidence += 1
            if local_evidence and profile.simplified_counts[simplified] >= 2:
                confidence = Confidence.HIGH
                score = 0.96
                reason = "全文简体风格明显，转换后的词语在全文其他位置有相同写法"
            elif profile.simplified_counts[simplified] >= 5 and profile.simplified_ratio > 0.995:
                confidence = Confidence.MEDIUM
                score = 0.72
                reason = "全文以简体为主，该繁体字可能是输入异常，但上下文证据不足"
            else:
                confidence = Confidence.LOW
                score = 0.35
                reason = "疑似繁简体混用，但可能是人名、专有名词或作者用法，保留原文"

        issues.append(
            TextIssue(
                chapter=chapter,
                category="traditional_character",
                confidence=confidence,
                confidence_score=score,
                rule="contextual_traditional_character",
                reason=reason,
                original=char,
                replacement=simplified,
                action="replace" if confidence == Confidence.HIGH else "report",
                paragraph=paragraph_index,
            )
        )

    return issues

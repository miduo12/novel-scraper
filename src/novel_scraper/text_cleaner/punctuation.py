from __future__ import annotations

import re

from .models import Confidence, TextIssue

_CJK = r"\u4e00-\u9fff"
_CJK_OR_QUOTE = r"\u4e00-\u9fff\u201c\u201d\"'"
_URL_OR_EMAIL = re.compile(r"(?:https?://|www\.|[\w.+-]+@[\w.-]+\.\w+)")


def _issue(
    chapter: str,
    paragraph_index: int,
    rule: str,
    reason: str,
    confidence: Confidence,
    score: float,
    original: str,
    replacement: str,
    action: str = "replace",
) -> TextIssue:
    return TextIssue(
        chapter=chapter,
        category="punctuation",
        confidence=confidence,
        confidence_score=score,
        rule=rule,
        reason=reason,
        original=original,
        replacement=replacement,
        action=action,
        paragraph=paragraph_index,
    )


def _apply(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    issues: list[TextIssue],
    chapter: str,
    paragraph_index: int,
    rule: str,
    reason: str,
    confidence: Confidence,
    score: float,
) -> str:
    matches = list(pattern.finditer(text))
    if not matches:
        return text
    for match in matches:
        replacement_text = match.expand(replacement)
        issues.append(
            _issue(
                chapter,
                paragraph_index,
                rule,
                reason,
                confidence,
                score,
                match.group(0),
                replacement_text,
            )
        )
    return pattern.sub(replacement, text)


def _is_english_or_url(paragraph: str) -> bool:
    if _URL_OR_EMAIL.search(paragraph):
        return True
    cjk_count = sum(1 for char in paragraph if "\u4e00" <= char <= "\u9fff")
    latin_count = sum(1 for char in paragraph if char.isascii() and char.isalpha())
    return latin_count >= 20 and latin_count > cjk_count * 2


def clean_paragraph(
    paragraph: str,
    chapter: str,
    paragraph_index: int,
) -> tuple[str, list[TextIssue]]:
    if not paragraph or _is_english_or_url(paragraph):
        return paragraph, []

    issues: list[TextIssue] = []
    text = paragraph

    text = _apply(
        text,
        re.compile(r"，{2,}"),
        "，",
        issues,
        chapter,
        paragraph_index,
        "repeated_cjk_comma",
        "连续重复逗号属于明显标点异常",
        Confidence.HIGH,
        0.98,
    )
    text = _apply(
        text,
        re.compile(r"。{2,}"),
        "。",
        issues,
        chapter,
        paragraph_index,
        "repeated_cjk_period",
        "连续重复句号属于明显标点异常",
        Confidence.HIGH,
        0.98,
    )

    mixed_rules = [
        (
            re.compile(rf"(?<=[{_CJK}])\s*,\s*(?=[{_CJK_OR_QUOTE}])"),
            "，",
            "ascii_comma_in_chinese",
            "中文语境中的英文逗号明显不匹配",
            0.95,
        ),
        (
            re.compile(rf"(?<=[{_CJK}])\s*\.\s*(?=$|[{_CJK_OR_QUOTE}])"),
            "。",
            "ascii_period_in_chinese",
            "中文语境中的英文句号明显不匹配",
            0.95,
        ),
        (
            re.compile(rf"(?<=[{_CJK}])\s*\?\s*(?=$|[{_CJK_OR_QUOTE}])"),
            "？",
            "ascii_question_in_chinese",
            "中文语境中的英文问号明显不匹配",
            0.95,
        ),
        (
            re.compile(rf"(?<=[{_CJK}])\s*!\s*(?=$|[{_CJK_OR_QUOTE}])"),
            "！",
            "ascii_exclamation_in_chinese",
            "中文语境中的英文叹号明显不匹配",
            0.95,
        ),
    ]
    for pattern, replacement, rule, reason, score in mixed_rules:
        text = _apply(
            text,
            pattern,
            replacement,
            issues,
            chapter,
            paragraph_index,
            rule,
            reason,
            Confidence.HIGH,
            score,
        )

    text = _apply(
        text,
        re.compile(rf"(?<=[{_CJK}])\s*\.{{3,}}\s*(?=$|[{_CJK_OR_QUOTE}])"),
        "……",
        issues,
        chapter,
        paragraph_index,
        "ascii_ellipsis_in_chinese",
        "中文语境中的连续英文句点是明显省略号写法",
        Confidence.HIGH,
        0.93,
    )
    text = _normalize_straight_quotes(text, chapter, paragraph_index, issues)

    repeated_expression = re.compile(r"[！!]{3,}|[？?]{3,}")
    for match in repeated_expression.finditer(text):
        issues.append(
            _issue(
                chapter,
                paragraph_index,
                "long_repeated_expression",
                "连续多个感叹号或问号可能是作者表达，保留原文",
                Confidence.LOW,
                0.35,
                match.group(0),
                match.group(0),
                action="report",
            )
        )

    if text.count("“") != text.count("”"):
        issues.append(
            _issue(
                chapter,
                paragraph_index,
                "unmatched_chinese_quotes",
                "中文引号数量不配对，无法可靠判断修改位置，保留原文",
                Confidence.MEDIUM,
                0.55,
                paragraph,
                paragraph,
                action="report",
            )
        )

    return text, issues


def _replace_straight_quotes(text: str) -> str:
    if text.count('"') == 0:
        return text
    if text.count("“") > text.count("”") and text.count('"') == 1:
        return text.replace('"', "”", 1)
    if text.count("”") > text.count("“") and text.count('"') == 1:
        return text.replace('"', "“", 1)

    chars = list(text)
    opening = True
    changed = False
    for index, char in enumerate(chars):
        if char != '"':
            continue
        chars[index] = "“" if opening else "”"
        opening = not opening
        changed = True
    return "".join(chars) if changed and not opening else text


def _normalize_straight_quotes(
    text: str,
    chapter: str,
    paragraph_index: int,
    issues: list[TextIssue],
) -> str:
    if '"' not in text:
        return text
    normalized = _replace_straight_quotes(text)
    if normalized == text:
        return text
    issues.append(
        _issue(
            chapter,
            paragraph_index,
            "straight_quote_in_chinese",
            "中文段落中的直引号可保守替换为成对中文引号",
            Confidence.HIGH,
            0.9,
            text,
            normalized,
        )
    )
    return normalized

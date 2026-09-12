from __future__ import annotations

import re

from .models import Confidence, TextIssue
from .rules import CleanerRules


def _first_match(paragraph: str, patterns: list[str]) -> str:
    for pattern in patterns:
        try:
            match = re.search(pattern, paragraph)
        except re.error:
            continue
        if match:
            return match.group(0)
    return ""


def detect_ad(
    paragraph: str,
    chapter: str,
    rules: CleanerRules,
    paragraph_index: int,
) -> TextIssue | None:
    paragraph = paragraph.strip()
    if not paragraph:
        return None
    if any(term and term in paragraph for term in rules.whitelist):
        return None

    strong = _first_match(paragraph, rules.strong_phrases)
    if strong:
        return TextIssue(
            chapter=chapter,
            category="advertisement",
            confidence=Confidence.HIGH,
            confidence_score=0.99,
            rule="strong_promotion_phrase",
            reason="包含明确的网站推广或公众号广告语句",
            original=strong,
            replacement="",
            action="delete",
            paragraph=paragraph_index,
        )

    url_matches: list[str] = []
    for pattern in (rules.url_pattern, rules.domain_pattern):
        if not pattern:
            continue
        try:
            url_matches.extend(match.group(0) for match in re.finditer(pattern, paragraph))
        except re.error:
            continue

    if url_matches:
        promo = any(cue and cue in paragraph for cue in rules.promo_cues)
        mostly_link = _mostly_link(paragraph, url_matches)
        if len(paragraph) <= 320 and (promo or len(url_matches) >= 2 or mostly_link):
            return TextIssue(
                chapter=chapter,
                category="advertisement",
                confidence=Confidence.HIGH,
                confidence_score=0.98,
                rule="promotional_url",
                reason="短段落中包含网址，并带有明显的推广特征",
                original=paragraph,
                replacement="",
                action="delete",
                paragraph=paragraph_index,
            )
        return TextIssue(
            chapter=chapter,
            category="advertisement",
            confidence=Confidence.MEDIUM,
            confidence_score=0.62,
            rule="url_in_text",
            reason="正文中出现网址，但上下文不足以确定为广告，保留原文",
            original=paragraph,
            replacement="",
            action="report",
            paragraph=paragraph_index,
        )

    soft_hits = sum(1 for cue in rules.soft_cues if cue and cue in paragraph)
    if soft_hits >= 3 and len(paragraph) <= 220:
        return TextIssue(
            chapter=chapter,
            category="advertisement",
            confidence=Confidence.MEDIUM,
            confidence_score=0.58,
            rule="multiple_soft_promotion_cues",
            reason="段落包含多个推广相关词语，疑似广告但保留原文",
            original=paragraph,
            replacement="",
            action="report",
            paragraph=paragraph_index,
        )
    return None


def _mostly_link(paragraph: str, links: list[str]) -> bool:
    remainder = paragraph
    for link in links:
        remainder = remainder.replace(link, "")
    remainder = re.sub(r"[\s，。！？；：、（）()【】\[\]<>《》\"']+", "", remainder)
    return len(remainder) <= 8

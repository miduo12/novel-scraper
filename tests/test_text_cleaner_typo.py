from novel_scraper.text_cleaner.cleaner import ChapterCleaner
from novel_scraper.text_cleaner.models import CleaningMode, Confidence
from novel_scraper.text_cleaner.rules import load_rules
from novel_scraper.text_cleaner.typo import TextStyleProfile, find_issues


def test_traditional_character_with_context_evidence_is_high_confidence() -> None:
    rules = load_rules()
    texts = ["这是正常的。", "這是异常的。", "这是第一次。"]
    profile = TextStyleProfile.build(texts, rules.traditional_map)
    issues = find_issues("這是异常的。", "第1章", 0, profile, rules)
    target = next(issue for issue in issues if issue.original == "這")
    assert target.confidence == Confidence.HIGH
    assert target.replacement == "这"


def test_rare_traditional_name_is_not_auto_changed() -> None:
    rules = load_rules()
    texts = ["张三来了。", "張三离开了。"]
    profile = TextStyleProfile.build(texts, rules.traditional_map)
    result = ChapterCleaner(rules).clean_chapter(
        "第1章",
        "test.txt",
        "張三离开了。",
        CleaningMode.AUTO,
        profile,
    )
    target = next(issue for issue in result.issues if issue.original == "張")
    assert target.confidence != Confidence.HIGH
    assert not target.applied
    assert result.cleaned_text == "張三离开了。"


def test_garbled_character_is_removed_in_auto_mode() -> None:
    rules = load_rules()
    profile = TextStyleProfile.build(["正文�测试"], rules.traditional_map)
    result = ChapterCleaner(rules).clean_chapter(
        "第1章",
        "test.txt",
        "正文�测试",
        CleaningMode.AUTO,
        profile,
    )
    assert result.cleaned_text == "正文测试"
    assert result.applied_count == 1

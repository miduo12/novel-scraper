from novel_scraper.text_cleaner.ads import detect_ad
from novel_scraper.text_cleaner.models import Confidence
from novel_scraper.text_cleaner.rules import load_rules


def test_high_confidence_promotion_is_detected() -> None:
    rules = load_rules()
    issue = detect_ad(
        "本章由测试小说网提供，请记住本站网址并收藏。",
        "第1章",
        rules,
        0,
    )
    assert issue is not None
    assert issue.confidence == Confidence.HIGH
    assert issue.rule == "strong_promotion_phrase"


def test_short_promotional_url_is_detected() -> None:
    rules = load_rules()
    issue = detect_ad("请访问 http://ads.example.com 获取最新章节", "第1章", rules, 0)
    assert issue is not None
    assert issue.confidence == Confidence.HIGH


def test_normal_wechat_and_website_are_not_deleted() -> None:
    rules = load_rules()
    paragraph = "他打开微信，网站页面显示正常，继续查看小说资料。"
    issue = detect_ad(paragraph, "第1章", rules, 0)
    assert issue is None


def test_whitelist_prevents_ad_deletion() -> None:
    rules = load_rules()
    rules.whitelist = ["本章由测试小说网提供"]
    issue = detect_ad(
        "本章由测试小说网提供，请记住本站网址。",
        "第1章",
        rules,
        0,
    )
    assert issue is None

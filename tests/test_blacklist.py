from pathlib import Path

import pytest

from novel_scraper.text_cleaner.ads import detect_ad
from novel_scraper.text_cleaner.blacklist import (
    AdBlacklistStore,
    find_blacklist_match,
)
from novel_scraper.text_cleaner.models import Confidence
from novel_scraper.text_cleaner.rules import load_rules


def test_blacklist_store_add_deduplicate_and_remove(tmp_path: Path) -> None:
    store = AdBlacklistStore(tmp_path / "ad_blacklist.json")
    first = store.add("本章由测试小说网提供，请记住本站网址。")
    duplicate = store.add("本章由测试小说网提供，请记住本站网址。")

    assert first.id == duplicate.id
    assert len(store.load()) == 1
    assert store.remove(first.id) is True
    assert store.load() == []


def test_blacklist_short_text_is_rejected(tmp_path: Path) -> None:
    store = AdBlacklistStore(tmp_path / "ad_blacklist.json")
    with pytest.raises(ValueError):
        store.add("广告")


def test_blacklist_fuzzy_match_detects_high_overlap(tmp_path: Path) -> None:
    store = AdBlacklistStore(tmp_path / "ad_blacklist.json")
    store.add("本章由测试小说网提供，请记住本站网址并收藏。")
    paragraph = "本章由测试小说网提供，请记住本站网址，马上收藏！"

    match = find_blacklist_match(paragraph, store.load())

    assert match is not None
    assert match.score >= 0.88


def test_blacklist_match_integrates_with_ad_detector(tmp_path: Path) -> None:
    store = AdBlacklistStore(tmp_path / "ad_blacklist.json")
    store.add("本章由测试小说网提供，请记住本站网址并收藏。")
    issue = detect_ad(
        "本章由测试小说网提供，请记住本站网址，马上收藏！",
        "第1章",
        load_rules(),
        0,
        store.load(),
    )

    assert issue is not None
    assert issue.confidence == Confidence.HIGH
    assert issue.rule == "user_ad_blacklist"
    assert issue.action == "delete"


def test_blacklist_does_not_delete_normal_text(tmp_path: Path) -> None:
    store = AdBlacklistStore(tmp_path / "ad_blacklist.json")
    store.add("本章由测试小说网提供，请记住本站网址并收藏。")
    issue = detect_ad(
        "他打开微信，和同学讨论小说里的情节。",
        "第1章",
        load_rules(),
        0,
        store.load(),
    )
    assert issue is None

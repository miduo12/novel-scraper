from novel_scraper.text_cleaner.models import Confidence
from novel_scraper.text_cleaner.punctuation import clean_paragraph, detect_web_residue


def test_fixes_ascii_comma_in_chinese_context() -> None:
    text, issues = clean_paragraph("你好,他说。", "第1章", 0)
    assert text == "你好，他说。"
    assert issues[0].confidence == Confidence.HIGH


def test_fixes_ascii_period_in_chinese_context() -> None:
    text, _ = clean_paragraph("他说道.", "第1章", 0)
    assert text == "他说道。"


def test_fixes_mixed_quotes_and_ascii_question() -> None:
    text, _ = clean_paragraph('“你说什么?"', "第1章", 0)
    assert text == "“你说什么？”"


def test_collapses_repeated_comma_and_period() -> None:
    text, issues = clean_paragraph("他来了，，，然后走了。。", "第1章", 0)
    assert text == "他来了，然后走了。"
    assert len(issues) == 2


def test_keeps_normal_literary_exclamation_and_question() -> None:
    text, issues = clean_paragraph("“不！！你怎么会知道？？？”", "第1章", 0)
    assert text == "“不！！你怎么会知道？？？”"
    assert any(issue.confidence == Confidence.LOW for issue in issues)


def test_keeps_english_sentence() -> None:
    text, issues = clean_paragraph("Hello, world. This is normal English.", "第1章", 0)
    assert text == "Hello, world. This is normal English."
    assert issues == []


def test_keeps_english_content_inside_chinese_quotes() -> None:
    text, _ = clean_paragraph("他说：“Hello, world.”", "第1章", 0)
    assert text == "他说：“Hello, world.”"


def test_cleans_mixed_dashes_and_escaped_closing_quote() -> None:
    source = '「但———-可惜了，身为穷人的他，注定会成为我们的狗。\\"'
    text, issues = clean_paragraph(source, "第1章", 0)
    assert text == "「但——可惜了，身为穷人的他，注定会成为我们的狗。」"
    assert any(issue.rule == "mixed_dash_sequence" for issue in issues)
    assert any(issue.rule == "escaped_quote_artifact" for issue in issues)


def test_detects_standalone_page_number_and_escape_fragment() -> None:
    number_issue = detect_web_residue("1", "第1章", 0, paragraph_count=5)
    escape_issue = detect_web_residue('\\"', "第1章", 1, paragraph_count=5)

    assert number_issue is not None
    assert number_issue.confidence == Confidence.HIGH
    assert number_issue.action == "remove"
    assert escape_issue is not None
    assert escape_issue.confidence == Confidence.HIGH


def test_cleans_multiple_backslashes_before_quote() -> None:
    source = '「但———-可惜了，注定会成为我们的狗。\\\\"'
    text, _ = clean_paragraph(source, "第1章", 0)
    assert text == "「但——可惜了，注定会成为我们的狗。」"

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea

from novel_scraper.blacklist_gui import AdBlacklistDialog
from novel_scraper.cleaner_gui import CleanerDialog
from novel_scraper.gui import MainWindow
from novel_scraper.review_gui import ReviewDialog
from novel_scraper.text_cleaner.models import (
    BookCleanResult,
    ChapterCleanResult,
    CleaningMode,
    Confidence,
    TextIssue,
)


def test_main_window_can_be_created() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.windowTitle().startswith("小说下载器")
    assert window.start_button.isEnabled()
    assert not window.stop_button.isEnabled()
    window.range_checkbox.setChecked(False)
    assert not window.start_spin.isEnabled()
    assert window.speed_combo.currentData() in {0.05, 0.2, 0.5}
    assert window.minimumHeight() >= 650
    assert isinstance(window.centralWidget(), QScrollArea)
    window.range_checkbox.setChecked(True)
    window.to_end_checkbox.setChecked(True)
    window.start_spin.setValue(11)
    assert window._selected_chapter_range() == (11, None)
    window.to_end_checkbox.setChecked(False)
    window.end_spin.setValue(20)
    assert window._selected_chapter_range() == (11, 20)
    dialog = CleanerDialog(window)
    assert dialog.windowTitle() == "小说内容检测与保守清洗"
    assert dialog.mode_combo.count() == 2
    dialog.close()
    window.close()
    app.processEvents()


def test_review_dialog_can_be_created(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    chapter = ChapterCleanResult("第1章", tmp_path / "1.txt", "他说道.", "他说道。")
    result = BookCleanResult(
        book_dir=tmp_path,
        mode=CleaningMode.AUTO,
        chapter_count=1,
        chapters=[chapter],
    )
    dialog = ReviewDialog(result)
    assert dialog.chapter_tree.topLevelItemCount() == 1
    assert dialog.change_table.rowCount() == 1
    assert dialog.chapter_tree.topLevelItem(0).toolTip(0).startswith("<html")
    dialog.close()
    app.processEvents()


def test_blacklist_dialog_can_be_created() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = AdBlacklistDialog(initial_text="测试广告文本，请访问网站。")
    assert dialog.windowTitle() == "广告黑名单"
    assert "测试广告文本" in dialog.text_input.toPlainText()
    dialog.close()
    app.processEvents()


def test_review_dialog_shows_report_only_issues(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    issues = [
        TextIssue(
            chapter="第1章",
            category="punctuation",
            confidence=Confidence.LOW,
            confidence_score=0.35,
            rule="long_repeated_expression",
            reason="连续多个标点可能是作者表达，保留原文",
            original="！！！",
            replacement="！！！",
            action="report",
            applied=False,
            paragraph=0,
        )
        for _ in range(16)
    ]
    chapter = ChapterCleanResult("第1章", tmp_path / "1.txt", "正文！！！", "正文！！！", issues)
    result = BookCleanResult(
        book_dir=tmp_path,
        mode=CleaningMode.DETECT,
        chapter_count=1,
        chapters=[chapter],
        issue_counts={"punctuation": 16},
    )
    dialog = ReviewDialog(result)
    assert dialog.chapter_tree.topLevelItem(0).text(1) == "16"
    assert dialog.change_table.rowCount() == 16
    assert dialog.change_table.item(0, 0).text() == "仅报告"
    dialog.close()
    app.processEvents()


def test_medium_confidence_issue_can_be_selected(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    issue = TextIssue(
        chapter="第1章",
        category="punctuation",
        confidence=Confidence.MEDIUM,
        confidence_score=0.72,
        rule="ascii_comma_in_chinese",
        reason="可能是英文逗号，建议人工确认",
        original=", ",
        replacement="，",
        action="report",
        applied=False,
        paragraph=0,
    )
    chapter = ChapterCleanResult(
        "第1章",
        tmp_path / "1.txt",
        "你好, 他说。",
        "你好, 他说。",
        [issue],
    )
    result = BookCleanResult(
        book_dir=tmp_path,
        mode=CleaningMode.DETECT,
        chapter_count=1,
        chapters=[chapter],
        issue_counts={"punctuation": 1},
    )
    dialog = ReviewDialog(result)
    check = dialog.change_table.item(0, 0)
    assert check.text() == ""
    assert bool(check.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert check.checkState() == Qt.CheckState.Unchecked
    dialog.close()
    app.processEvents()

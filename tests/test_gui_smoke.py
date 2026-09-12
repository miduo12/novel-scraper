import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from novel_scraper.cleaner_gui import CleanerDialog
from novel_scraper.review_gui import ReviewDialog
from novel_scraper.text_cleaner.models import BookCleanResult, ChapterCleanResult, CleaningMode
from novel_scraper.gui import MainWindow


def test_main_window_can_be_created() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.windowTitle().startswith("小说下载器")
    assert window.start_button.isEnabled()
    assert not window.stop_button.isEnabled()
    assert not window.range_checkbox.isChecked()
    assert not window.start_spin.isEnabled()
    assert window.speed_combo.currentData() == 0.2
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
    dialog.close()
    app.processEvents()

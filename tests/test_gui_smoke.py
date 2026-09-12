import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from novel_scraper.gui import MainWindow


def test_main_window_can_be_created() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.windowTitle().startswith("小说下载器")
    assert window.start_button.isEnabled()
    assert not window.stop_button.isEnabled()
    window.close()
    app.processEvents()

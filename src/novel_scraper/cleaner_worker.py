from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .text_cleaner import BookCleaner, BookCleanResult, CleaningMode


class CleanWorker(QThread):
    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, book_dir: Path, mode: CleaningMode, parent=None) -> None:
        super().__init__(parent)
        self.book_dir = book_dir
        self.mode = mode

    def run(self) -> None:
        try:
            cleaner = BookCleaner()
            result = cleaner.process(
                self.book_dir,
                self.mode,
                progress_callback=self.progress.emit,
                persist_output=False,
            )
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or exc.__class__.__name__)


class CleanSaveWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, result: BookCleanResult, parent=None) -> None:
        super().__init__(parent)
        self.result = result

    def run(self) -> None:
        try:
            result = BookCleaner().save_output(self.result)
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or exc.__class__.__name__)

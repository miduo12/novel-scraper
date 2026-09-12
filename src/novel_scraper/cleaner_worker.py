from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .text_cleaner import BookCleaner, CleaningMode


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
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)

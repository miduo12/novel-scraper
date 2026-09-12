from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QWidget


def apply_adaptive_size(
    widget: QWidget,
    preferred_width: int,
    preferred_height: int,
    *,
    available_ratio: float = 0.92,
) -> None:
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    if screen is None:
        widget.resize(preferred_width, preferred_height)
        return
    available = screen.availableGeometry()
    width = min(preferred_width, max(640, int(available.width() * available_ratio)))
    height = min(preferred_height, max(520, int(available.height() * available_ratio)))
    widget.resize(width, height)

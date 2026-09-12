from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .text_cleaner.blacklist import AdBlacklistStore, normalize_match_text


class AdBlacklistDialog(QDialog):
    entries_changed = Signal()

    def __init__(self, parent=None, *, initial_text: str = "") -> None:
        super().__init__(parent)
        self.store = AdBlacklistStore()
        self.setWindowTitle("广告黑名单")
        self.resize(760, 560)
        self._build_ui()
        self._refresh()
        if initial_text:
            self.text_input.setPlainText(initial_text.strip())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("广告黑名单")
        title.setObjectName("title")
        description = QLabel(
            "粘贴未删除的广告文本。以后检测时会对段落做标准化和相似度比对，"
            "高度重合的内容自动删除，中等重合只报告。"
        )
        description.setObjectName("subtitle")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText("在这里粘贴广告原文，尽量保留完整段落。")
        self.text_input.setMinimumHeight(130)
        layout.addWidget(self.text_input)

        input_buttons = QHBoxLayout()
        paste_button = QPushButton("从剪贴板粘贴")
        paste_button.setObjectName("secondaryButton")
        paste_button.clicked.connect(self._paste)
        add_button = QPushButton("加入黑名单")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add)
        input_buttons.addWidget(paste_button)
        input_buttons.addWidget(add_button)
        input_buttons.addStretch(1)
        layout.addLayout(input_buttons)

        list_label = QLabel("已有黑名单")
        list_label.setObjectName("sectionTitle")
        layout.addWidget(list_label)

        self.entry_list = QListWidget()
        self.entry_list.itemDoubleClicked.connect(lambda _item: self._remove())
        layout.addWidget(self.entry_list, 1)

        bottom = QHBoxLayout()
        remove_button = QPushButton("删除选中")
        remove_button.setObjectName("dangerButton")
        remove_button.clicked.connect(self._remove)
        close_button = QPushButton("关闭")
        close_button.setObjectName("secondaryButton")
        close_button.clicked.connect(self.accept)
        self.status_label = QLabel("")
        self.status_label.setObjectName("footer")
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(remove_button)
        bottom.addWidget(close_button)
        layout.addLayout(bottom)

    def _paste(self) -> None:
        text = QApplication.clipboard().text().strip()
        if text:
            self.text_input.setPlainText(text)

    def _add(self) -> None:
        text = self.text_input.toPlainText().strip()
        try:
            entry = self.store.add(text)
        except ValueError as exc:
            QMessageBox.warning(self, "内容过短", str(exc))
            return
        self.text_input.clear()
        self.status_label.setText(f"已加入：{len(normalize_match_text(entry.text))} 个有效字符")
        self._refresh()
        self.entries_changed.emit()

    def _remove(self) -> None:
        item = self.entry_list.currentItem()
        if item is None:
            return
        entry_id = str(item.data(Qt.ItemDataRole.UserRole))
        self.store.remove(entry_id)
        self.status_label.setText("已删除所选黑名单")
        self._refresh()
        self.entries_changed.emit()

    def _refresh(self) -> None:
        self.entry_list.clear()
        entries = self.store.load()
        for entry in entries:
            preview = " ".join(entry.text.split())
            if len(preview) > 90:
                preview = preview[:89] + "…"
            item = QListWidgetItem(preview)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            item.setToolTip(entry.text)
            self.entry_list.addItem(item)
        self.status_label.setText(f"共 {len(entries)} 条黑名单；文件：{self.store.path}")

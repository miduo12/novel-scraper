from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .blacklist_gui import AdBlacklistDialog
from .cleaner_worker import CleanWorker
from .review_gui import ReviewDialog
from .text_cleaner import BookCleanResult, CleanProgress, CleaningMode


class CleanerDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.worker: CleanWorker | None = None
        self.last_result: BookCleanResult | None = None
        self.setWindowTitle("小说内容检测与保守清洗")
        self.resize(820, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("小说内容检测与保守清洗")
        title.setObjectName("title")
        description = QLabel(
            "选择包含 chapters/ 的已下载小说文件夹。原始章节不会被覆盖，"
            "清洗结果和报告会写入 cleaned/ 与 reports/。"
        )
        description.setObjectName("subtitle")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        directory_row = QHBoxLayout()
        self.directory_input = QLineEdit()
        self.directory_input.setPlaceholderText("选择小说文件夹，例如 .../小说下载/玄鉴仙族")
        self.directory_input.setMinimumHeight(40)
        browse_button = QPushButton("选择文件夹")
        browse_button.setObjectName("secondaryButton")
        browse_button.clicked.connect(self._choose_directory)
        directory_row.addWidget(self.directory_input, 1)
        directory_row.addWidget(browse_button)
        layout.addLayout(directory_row)

        mode_row = QHBoxLayout()
        mode_label = QLabel("处理模式")
        mode_label.setObjectName("fieldLabel")
        self.mode_combo = QComboBox()
        self.mode_combo.setMinimumHeight(40)
        self.mode_combo.addItem("仅检测（不修改正文）", CleaningMode.DETECT.value)
        self.mode_combo.addItem("保守自动修复（仅高置信度）", CleaningMode.AUTO.value)
        self.mode_combo.setCurrentIndex(0)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_row)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("开始检测")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setMinimumHeight(44)
        self.start_button.clicked.connect(self._start)
        self.open_reports_button = QPushButton("打开报告目录")
        self.open_reports_button.setObjectName("secondaryButton")
        self.open_reports_button.setEnabled(False)
        self.open_reports_button.clicked.connect(self._open_reports)
        self.review_button = QPushButton("人工审核修改")
        self.review_button.setObjectName("secondaryButton")
        self.review_button.setEnabled(False)
        self.review_button.setToolTip("自动修复完成后查看并逐条审核修改")
        self.review_button.clicked.connect(self._open_review)
        self.blacklist_button = QPushButton("广告黑名单")
        self.blacklist_button.setObjectName("secondaryButton")
        self.blacklist_button.setToolTip("管理用户自定义广告文本，下次检测时自动比对")
        self.blacklist_button.clicked.connect(self._open_blacklist)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.review_button)
        button_row.addWidget(self.blacklist_button)
        button_row.addWidget(self.open_reports_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.status_label = QLabel("等待选择小说文件夹")
        self.status_label.setObjectName("chapterLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.document().setMaximumBlockCount(1000)
        layout.addWidget(self.log_output, 1)

        note = QLabel(
            "保守策略：高置信度问题才自动修改；中低置信度问题只写入报告，"
            "无法确定的内容保持原文。"
        )
        note.setObjectName("footer")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择已下载小说文件夹",
            self.directory_input.text().strip() or str(Path.home()),
        )
        if selected:
            self.directory_input.setText(selected)

    def _start(self) -> None:
        book_dir = Path(self.directory_input.text().strip()).expanduser()
        if not (book_dir / "chapters").is_dir():
            QMessageBox.warning(self, "目录不正确", "请选择包含 chapters/ 子目录的小说文件夹。")
            return

        self.start_button.setEnabled(False)
        self.open_reports_button.setEnabled(False)
        self.review_button.setEnabled(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        self.last_result = None
        mode = CleaningMode(str(self.mode_combo.currentData()))
        self.status_label.setText("正在读取章节…")
        self.worker = CleanWorker(book_dir, mode, parent=self)
        self.worker.progress.connect(self._handle_progress)
        self.worker.succeeded.connect(self._handle_success)
        self.worker.failed.connect(self._handle_failure)
        self.worker.start()

    def _handle_progress(self, progress: CleanProgress) -> None:
        self.progress_bar.setRange(0, max(1, progress.total))
        self.progress_bar.setValue(progress.current)
        self.status_label.setText(
            f"[{progress.current}/{progress.total}] {progress.message}：{progress.chapter}"
        )
        self._append_log(f"[{progress.current}/{progress.total}] {progress.chapter} {progress.message}")

    def _handle_success(self, result: BookCleanResult) -> None:
        self.last_result = result
        self.worker = None
        self.start_button.setEnabled(True)
        self.open_reports_button.setEnabled(True)
        self.review_button.setEnabled(
            result.mode == CleaningMode.AUTO and result.applied_count > 0
        )
        self.progress_bar.setValue(self.progress_bar.maximum())
        summary = [
            f"章节：{result.chapter_count}",
            f"问题：{result.total_issues}",
            f"自动修改：{result.applied_count}",
            f"广告：{result.issue_counts.get('advertisement', 0)}",
            f"标点：{result.issue_counts.get('punctuation', 0)}",
            f"异常字符：{result.issue_counts.get('abnormal_character', 0)}",
            f"繁简异常：{result.issue_counts.get('traditional_character', 0)}",
        ]
        self.status_label.setText("检测完成：" + "，".join(summary))
        self._append_log("检测完成：" + "；".join(summary))
        self._append_log(f"报告目录：{result.reports_dir}")
        if result.cleaned_book_path:
            self._append_log(f"清洗版 TXT：{result.cleaned_book_path}")
        QMessageBox.information(self, "处理完成", "\n".join(summary))

    def _handle_failure(self, message: str) -> None:
        self.worker = None
        self.start_button.setEnabled(True)
        self.status_label.setText("处理失败")
        self._append_log(f"处理失败：{message}")
        QMessageBox.critical(self, "处理失败", message)

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def _open_blacklist(self) -> None:
        dialog = AdBlacklistDialog(self)
        dialog.exec()
        self._append_log("广告黑名单已更新，下次检测会自动应用")

    def _open_review(self) -> None:
        if self.last_result is None:
            return
        dialog = ReviewDialog(self.last_result, self)
        dialog.exec()
        self._append_log("人工审核完成，清洗版输出已按审核结果更新")

    def _open_reports(self) -> None:
        if self.last_result is None or self.last_result.reports_dir is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_result.reports_dir)))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "正在处理", "检测仍在运行，请等待完成后再关闭。")
            event.ignore()
            return
        event.accept()

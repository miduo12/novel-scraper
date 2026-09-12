from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .events import CrawlEvent
from .gui_worker import CrawlWorker
from .models import CrawlResult

APP_NAME = "小说下载器"
APP_ORGANIZATION = "miduo12"


def resource_path(filename: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    if getattr(sys, "frozen", False):
        return base / "novel_scraper" / "resources" / filename
    return Path(__file__).resolve().parent / "resources" / filename


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(APP_ORGANIZATION, "NovelScraper")
        self.worker: CrawlWorker | None = None
        self.last_output_path: Path | None = None
        self.last_combined_path: Path | None = None
        self._chapter_total = 0
        self._closing = False
        self._build_ui()
        self._restore_settings()
        self.setAcceptDrops(True)

    def _build_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(900, 680)
        self.setMinimumSize(760, 560)

        icon_path = resource_path("app.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(30, 26, 30, 24)
        root.setSpacing(18)

        title = QLabel(APP_NAME)
        title.setObjectName("title")
        subtitle = QLabel("粘贴小说目录链接，一键下载为 TXT。支持断点续传和失败重试。")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        input_card = QFrame()
        input_card.setObjectName("card")
        form = QVBoxLayout(input_card)
        form.setContentsMargins(22, 20, 22, 20)
        form.setSpacing(10)

        url_label = QLabel("小说目录或章节网址")
        url_label.setObjectName("fieldLabel")
        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText("例如：https://www.deqixs.cc/books/99/")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setMinimumHeight(42)
        form.addWidget(url_label)
        form.addWidget(self.url_input)

        output_label = QLabel("保存位置")
        output_label.setObjectName("fieldLabel")
        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        self.output_input = QLineEdit()
        self.output_input.setObjectName("outputInput")
        self.output_input.setMinimumHeight(40)
        browse_button = QPushButton("选择文件夹")
        browse_button.setObjectName("secondaryButton")
        browse_button.clicked.connect(self._choose_output_dir)
        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(browse_button)
        form.addWidget(output_label)
        form.addLayout(output_row)

        speed_label = QLabel("下载速度")
        speed_label.setObjectName("fieldLabel")
        self.speed_combo = QComboBox()
        self.speed_combo.setObjectName("speedCombo")
        self.speed_combo.setMinimumHeight(40)
        self.speed_combo.addItem("稳定（0.5 秒）", 0.5)
        self.speed_combo.addItem("快速（0.2 秒，推荐）", 0.2)
        self.speed_combo.addItem("极速（0.05 秒，谨慎）", 0.05)
        self.speed_combo.setCurrentIndex(1)
        form.addWidget(speed_label)
        form.addWidget(self.speed_combo)

        range_label = QLabel("章节范围")
        range_label.setObjectName("fieldLabel")
        range_row = QHBoxLayout()
        range_row.setSpacing(8)
        self.range_checkbox = QCheckBox("仅下载指定范围")
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 999999)
        self.start_spin.setValue(1)
        self.start_spin.setPrefix("第 ")
        self.start_spin.setSuffix(" 章")
        self.start_spin.setMinimumWidth(115)
        self.end_spin = QSpinBox()
        self.end_spin.setRange(1, 999999)
        self.end_spin.setValue(1)
        self.end_spin.setPrefix("第 ")
        self.end_spin.setSuffix(" 章")
        self.end_spin.setMinimumWidth(115)
        range_to = QLabel("至")
        range_row.addWidget(self.range_checkbox)
        range_row.addStretch(1)
        range_row.addWidget(self.start_spin)
        range_row.addWidget(range_to)
        range_row.addWidget(self.end_spin)
        form.addWidget(range_label)
        form.addLayout(range_row)
        self.range_checkbox.toggled.connect(self._toggle_chapter_range)
        self._toggle_chapter_range(False)

        output_note = QLabel("完成后会同时保存 chapters/ 分章 TXT 和书籍根目录下的整本 TXT。")
        output_note.setObjectName("helperLabel")
        output_note.setWordWrap(True)
        form.addWidget(output_note)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.start_button = QPushButton("开始下载")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setMinimumHeight(46)
        self.start_button.clicked.connect(self._start_download)
        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setMinimumHeight(46)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_download)
        self.open_button = QPushButton("打开文件夹")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.setMinimumHeight(46)
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_output_dir)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.stop_button)
        action_row.addWidget(self.open_button)
        form.addLayout(action_row)
        root.addWidget(input_card)

        status_card = QFrame()
        status_card.setObjectName("card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(22, 18, 22, 18)
        status_layout.setSpacing(9)

        status_header = QHBoxLayout()
        self.book_label = QLabel("等待开始")
        self.book_label.setObjectName("bookLabel")
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setObjectName("progressLabel")
        status_header.addWidget(self.book_label, 1)
        status_header.addWidget(self.progress_label)
        self.chapter_label = QLabel("输入网址后点击“开始下载”")
        self.chapter_label.setObjectName("chapterLabel")
        self.chapter_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        status_layout.addLayout(status_header)
        status_layout.addWidget(self.chapter_label)
        status_layout.addWidget(self.progress_bar)
        root.addWidget(status_card)

        log_header = QHBoxLayout()
        log_title = QLabel("运行记录")
        log_title.setObjectName("sectionTitle")
        clear_button = QPushButton("清空")
        clear_button.setObjectName("linkButton")
        clear_button.clicked.connect(lambda: self.log_output.clear())
        log_header.addWidget(log_title)
        log_header.addStretch(1)
        log_header.addWidget(clear_button)
        root.addLayout(log_header)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        self.log_output.document().setMaximumBlockCount(1000)
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.log_output, 1)

        footer = QLabel("请合理设置请求频率，仅用于个人学习与备份，并遵守目标网站的服务条款。")
        footer.setObjectName("footer")
        footer.setWordWrap(True)
        root.addWidget(footer)

        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#central { background: #f3f6fb; color: #172033; }
            QLabel#title { font-size: 30px; font-weight: 700; color: #13213c; }
            QLabel#subtitle { font-size: 14px; color: #63708a; }
            QLabel#fieldLabel { font-size: 13px; font-weight: 600; color: #34425e; }
            QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #26344f; }
            QLabel#bookLabel { font-size: 16px; font-weight: 700; color: #1f3155; }
            QLabel#chapterLabel { font-size: 13px; color: #5f6f8c; }
            QLabel#progressLabel { font-size: 14px; font-weight: 700; color: #2f6fed; }
            QLabel#footer { font-size: 12px; color: #8a94a8; }
            QLabel#helperLabel { font-size: 12px; color: #71809b; }
            QFrame#card { background: white; border: 1px solid #e1e7f2; border-radius: 14px; }
            QLineEdit { border: 1px solid #cfd8e8; border-radius: 9px; padding: 8px 12px;
                        background: #fbfcff; font-size: 14px; selection-background-color: #2f6fed; }
            QLineEdit:focus { border: 2px solid #2f6fed; background: white; }
            QComboBox { border: 1px solid #cfd8e8; border-radius: 9px; padding: 8px 12px;
                        background: #fbfcff; font-size: 14px; color: #26344f; }
            QComboBox:focus { border: 2px solid #2f6fed; background: white; }
            QComboBox QAbstractItemView { background: white; color: #26344f; selection-background-color: #dbe7ff; }
            QSpinBox { border: 1px solid #cfd8e8; border-radius: 9px; padding: 7px 10px;
                        background: #fbfcff; font-size: 14px; color: #26344f; }
            QSpinBox:disabled { color: #9aa5b8; background: #f4f6f9; }
            QCheckBox { font-size: 13px; color: #34425e; spacing: 7px; }
            QPushButton { border-radius: 9px; padding: 9px 18px; font-size: 14px; font-weight: 600; }
            QPushButton#primaryButton { background: #2f6fed; color: white; border: none; min-width: 130px; }
            QPushButton#primaryButton:hover { background: #245bd0; }
            QPushButton#primaryButton:disabled { background: #adc1e9; }
            QPushButton#dangerButton { background: #fff0f0; color: #c33b3b; border: 1px solid #f1bcbc; }
            QPushButton#dangerButton:hover { background: #ffe2e2; }
            QPushButton#dangerButton:disabled { color: #b8b8b8; border-color: #e3e3e3; background: #f7f7f7; }
            QPushButton#secondaryButton { background: #edf2fb; color: #2e4d82; border: 1px solid #d9e2f2; }
            QPushButton#secondaryButton:hover { background: #e2eaf8; }
            QPushButton#secondaryButton:disabled { color: #9aa5b8; background: #f4f6f9; border-color: #e6e9ef; }
            QPushButton#linkButton { background: transparent; color: #65738d; border: none; padding: 4px 8px; }
            QPushButton#linkButton:hover { color: #2f6fed; }
            QProgressBar#progressBar { border: none; border-radius: 5px; background: #e7ecf6; }
            QProgressBar#progressBar::chunk { border-radius: 5px; background: #2f6fed; }
            QTextEdit#logOutput { background: #111827; color: #d7e0f1; border: none;
                                  border-radius: 12px; padding: 12px; font-family: Consolas, monospace;
                                  font-size: 12px; }
            """
        )

    def _restore_settings(self) -> None:
        last_url = str(self.settings.value("last_url", ""))
        self.url_input.setText(last_url)
        default_output = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        ) / "小说下载"
        self.output_input.setText(str(self.settings.value("output_dir", default_output)))
        saved_delay = float(self.settings.value("speed_delay", 0.2))
        speed_index = self.speed_combo.findData(saved_delay)
        self.speed_combo.setCurrentIndex(speed_index if speed_index >= 0 else 1)
        self.start_spin.setValue(int(self.settings.value("start_chapter", 1)))
        self.end_spin.setValue(int(self.settings.value("end_chapter", 1)))
        range_enabled = str(self.settings.value("range_enabled", "false")).lower() == "true"
        self.range_checkbox.setChecked(range_enabled)
        self._toggle_chapter_range(range_enabled)

    def _save_settings(self) -> None:
        self.settings.setValue("last_url", self.url_input.text().strip())
        self.settings.setValue("output_dir", self.output_input.text().strip())
        self.settings.setValue("speed_delay", float(self.speed_combo.currentData()))
        self.settings.setValue("range_enabled", self.range_checkbox.isChecked())
        self.settings.setValue("start_chapter", self.start_spin.value())
        self.settings.setValue("end_chapter", self.end_spin.value())

    def _toggle_chapter_range(self, enabled: bool) -> None:
        self.start_spin.setEnabled(enabled)
        self.end_spin.setEnabled(enabled)

    def _configure_chapter_range(
        self,
        total: int,
        first_number: int | None = None,
        last_number: int | None = None,
    ) -> None:
        self._chapter_total = total
        first = first_number or 1
        last = last_number or total
        old_end = self.end_spin.value()
        old_max = self.end_spin.maximum()
        self.start_spin.setRange(first, max(first, last))
        self.end_spin.setRange(first, max(first, last))
        if not self.range_checkbox.isChecked() or old_end in {1, old_max}:
            self.end_spin.setValue(last)

    def _choose_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择保存文件夹",
            self.output_input.text().strip() or str(Path.home()),
        )
        if selected:
            self.output_input.setText(selected)

    def _start_download(self) -> None:
        url = self.url_input.text().strip()
        output_text = self.output_input.text().strip()
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "网址不正确", "请粘贴完整的小说目录或章节网址。")
            return
        if "deqixs.cc" not in url:
            QMessageBox.warning(self, "暂不支持", "当前桌面版暂只适配得奇小说网 deqixs.cc。")
            return

        start_chapter = None
        end_chapter = None
        if self.range_checkbox.isChecked():
            start_chapter = self.start_spin.value()
            end_chapter = self.end_spin.value()
            if start_chapter > end_chapter:
                QMessageBox.warning(self, "章节范围不正确", "起始章节不能大于结束章节。")
                return

        try:
            output_dir = Path(output_text).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "无法创建保存目录", str(exc))
            return

        self._save_settings()
        self.last_output_path = output_dir
        self.open_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.url_input.setEnabled(False)
        self.output_input.setEnabled(False)
        self.speed_combo.setEnabled(False)
        self.range_checkbox.setEnabled(False)
        self.start_spin.setEnabled(False)
        self.end_spin.setEnabled(False)
        self.book_label.setText("正在解析小说目录…")
        self.chapter_label.setText("首次使用请保持网络连接")
        self.progress_label.setText("0 / 0")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        self._append_log("开始任务")

        self.worker = CrawlWorker(
            url,
            output_dir,
            delay=float(self.speed_combo.currentData()),
            retries=3,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            parent=self,
        )
        self.worker.event_received.connect(self._handle_event)
        self.worker.succeeded.connect(self._handle_success)
        self.worker.failed.connect(self._handle_failure)
        self.worker.stopped.connect(self._handle_stopped)
        self.worker.start()

    def _stop_download(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.stop_button.setEnabled(False)
            self.chapter_label.setText("正在停止，完成当前请求后会退出…")
            self._append_log("正在停止下载")
            self.worker.request_cancel()

    def _handle_event(self, event: CrawlEvent) -> None:
        if event.kind == "book_loaded":
            self._configure_chapter_range(
                event.book_total or event.total,
                event.first_chapter_number,
                event.last_chapter_number,
            )
        if event.book_title:
            self.book_label.setText(f"《{event.book_title}》  作者：{event.author or '未知'}")
        if event.total > 0:
            self.progress_bar.setRange(0, event.total)
            self.progress_bar.setValue(min(event.completed, event.total))
            self.progress_label.setText(f"{event.completed} / {event.total}")

        if event.kind == "chapter_started":
            self.chapter_label.setText(f"正在下载：{event.chapter_title}")
            self._append_log(f"[{event.completed + 1}/{event.total}] {event.chapter_title}")
        elif event.kind == "page_started":
            self.chapter_label.setText(f"{event.chapter_title} · 第 {event.page} 页")
            self._append_log(f"    第 {event.page} 页")
        elif event.kind == "chapter_completed":
            self.chapter_label.setText(f"已完成：{event.chapter_title}")
            self._append_log(f"    {event.message}")
        elif event.kind == "chapter_skipped":
            self.chapter_label.setText(f"已存在，跳过：{event.chapter_title}")
            self._append_log("    已存在，跳过")
        elif event.kind == "chapter_failed":
            self.chapter_label.setText(f"失败，继续下一章：{event.chapter_title}")
            self._append_log(f"    失败：{event.message}")
        elif event.kind == "finished":
            self._append_log(event.message)

    def _handle_success(self, result: CrawlResult) -> None:
        self.last_combined_path = Path(result.output_path)
        self.last_output_path = self.last_combined_path.parent
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.chapter_label.setText(f"整本 TXT：{self.last_combined_path}")
        self._append_log(f"分章目录：{result.chapters_path}")
        self._append_log(f"整本 TXT：{self.last_combined_path}")
        self._finish_ui()
        if not self._closing:
            QMessageBox.information(
                self,
                "下载完成",
                f"分章 TXT 目录：\n{result.chapters_path}\n\n整本 TXT：\n{self.last_combined_path}",
            )

    def _handle_failure(self, message: str) -> None:
        self.chapter_label.setText("任务失败，请查看运行记录")
        self._append_log(f"任务失败：{message}")
        self._finish_ui()
        if not self._closing:
            QMessageBox.critical(self, "下载失败", message)

    def _handle_stopped(self) -> None:
        self.chapter_label.setText("已停止，已完成章节会保留，下次可继续")
        self._append_log("任务已停止，进度已保留")
        self._finish_ui()
        if self._closing:
            QTimer.singleShot(0, self.close)

    def _finish_ui(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.url_input.setEnabled(True)
        self.output_input.setEnabled(True)
        self.speed_combo.setEnabled(True)
        self.range_checkbox.setEnabled(True)
        self._toggle_chapter_range(self.range_checkbox.isChecked())
        self.open_button.setEnabled(self.last_output_path is not None)
        self.worker = None

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def _open_output_dir(self) -> None:
        if self.last_output_path is None:
            return
        self.last_output_path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_path)))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        text = event.mimeData().text().strip()
        if text:
            self.url_input.setText(text)
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None and self.worker.isRunning():
            answer = QMessageBox.question(
                self,
                "任务仍在运行",
                "要停止下载并退出吗？已经完成的章节会保留。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._closing = True
                self.worker.request_cancel()
                self.chapter_label.setText("正在停止，请稍候…")
                event.ignore()
                return
            event.ignore()
            return
        event.accept()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novel-scraper-gui")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")

    window = MainWindow()
    if args.smoke_test:
        QTimer.singleShot(150, app.quit)
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

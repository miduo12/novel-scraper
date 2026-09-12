from __future__ import annotations

import difflib
from html import escape

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from .blacklist_gui import AdBlacklistDialog
from .text_cleaner.models import BookCleanResult, TextIssue
from .ui_utils import apply_adaptive_size
from .text_cleaner.review import (
    DiffChange,
    apply_review_decisions,
    build_diff_changes,
    write_reviewed_output,
)

_CATEGORY_LABELS = {
    "advertisement": "广告",
    "punctuation": "标点",
    "abnormal_character": "异常字符",
    "traditional_character": "繁简异常",
    "web_residue": "网页残留",
    "text_change": "文本修改",
}
_CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}


class ReviewDialog(QDialog):
    def __init__(self, result: BookCleanResult, parent=None) -> None:
        super().__init__(parent)
        self.result = result
        self.changes_by_chapter: dict[str, list[DiffChange]] = {}
        self.accepted: dict[str, dict[int, bool]] = {}
        self._updating = False
        self._current_chapter = ""
        self.issues_by_chapter: dict[str, list[TextIssue]] = {}
        self.setWindowTitle("人工审核自动修改")
        apply_adaptive_size(self, 1250, 850)
        self._build_ui()
        self._load_changes()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("人工审核自动修改")
        title.setObjectName("title")
        description = QLabel(
            "每条修改默认勾选。取消勾选后点击“应用审核结果”，对应位置会恢复原文；"
            "原始 chapters/ 不会被覆盖。"
        )
        description.setObjectName("subtitle")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setHeaderLabels(["章节", "修改数", "标点", "广告", "其他"])
        self.chapter_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.chapter_tree.setMinimumWidth(360)
        self.chapter_tree.setMouseTracking(True)
        self.chapter_tree.itemEntered.connect(self._show_chapter_tooltip)
        self.chapter_tree.currentItemChanged.connect(self._chapter_changed)
        splitter.addWidget(self.chapter_tree)

        right = QSplitter(Qt.Orientation.Vertical)
        self.change_table = QTableWidget(0, 6)
        self.change_table.setHorizontalHeaderLabels(
            ["应用", "类型", "置信度", "原文", "修改后", "原因"]
        )
        self.change_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        for column in (1, 2):
            self.change_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.change_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.change_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.change_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.change_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.change_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.change_table.setMouseTracking(True)
        self.change_table.cellEntered.connect(self._show_cell_tooltip)
        self.change_table.itemChanged.connect(self._change_checked)
        right.addWidget(self.change_table)

        self.preview = QTextBrowser()
        self.preview.setObjectName("reviewPreview")
        self.preview.setOpenExternalLinks(False)
        right.addWidget(self.preview)
        right.setSizes([420, 260])
        splitter.addWidget(right)
        splitter.setSizes([390, 790])
        layout.addWidget(splitter, 1)

        action_row = QHBoxLayout()
        select_all = QPushButton("全部勾选")
        select_all.setObjectName("secondaryButton")
        select_all.clicked.connect(lambda: self._set_all_checked(True))
        clear_all = QPushButton("全部取消")
        clear_all.setObjectName("secondaryButton")
        clear_all.clicked.connect(lambda: self._set_all_checked(False))
        apply_button = QPushButton("应用审核结果")
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._apply)
        self.open_reports = QPushButton("打开报告目录")
        self.open_reports.setObjectName("secondaryButton")
        self.open_reports.clicked.connect(self._open_reports)
        blacklist_button = QPushButton("选中文本加入黑名单")
        blacklist_button.setObjectName("secondaryButton")
        blacklist_button.setToolTip("可在下方预览中选择广告文本后加入黑名单")
        blacklist_button.clicked.connect(self._add_selected_to_blacklist)
        action_row.addWidget(select_all)
        action_row.addWidget(clear_all)
        action_row.addStretch(1)
        action_row.addWidget(blacklist_button)
        action_row.addWidget(self.open_reports)
        action_row.addWidget(apply_button)
        layout.addLayout(action_row)

        note = QLabel(
            "悬停章节或修改行可以查看更完整的上下文。取消的修改会写入 "
            "reports/review_decisions.json。"
        )
        note.setObjectName("footer")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _load_changes(self) -> None:
        self._updating = True
        self.chapter_tree.clear()
        for chapter in self.result.chapters:
            changes = build_diff_changes(chapter)
            applied_issues = [issue for issue in chapter.issues if issue.applied]
            self.changes_by_chapter[chapter.title] = changes
            self.issues_by_chapter[chapter.title] = applied_issues
            self.accepted[chapter.title] = {change.index: True for change in changes}
            counts: dict[str, int] = {}
            for issue in applied_issues:
                counts[issue.category] = counts.get(issue.category, 0) + 1
            item = QTreeWidgetItem(
                [
                    chapter.title,
                    str(len(applied_issues)),
                    str(counts.get("punctuation", 0)),
                    str(counts.get("advertisement", 0)),
                    str(
                        sum(
                            count
                            for category, count in counts.items()
                            if category not in {"punctuation", "advertisement"}
                        )
                    ),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, chapter.title)
            item.setToolTip(0, self._chapter_tooltip(chapter.title, changes, applied_issues))
            for column in range(5):
                item.setToolTip(column, item.toolTip(0))
            self.chapter_tree.addTopLevelItem(item)
        self._updating = False
        if self.chapter_tree.topLevelItemCount():
            self.chapter_tree.setCurrentItem(self.chapter_tree.topLevelItem(0))
        else:
            self.change_table.setRowCount(0)
            self.preview.setHtml("<p>没有可审核的自动修改。</p>")

    def _chapter_changed(self, current: QTreeWidgetItem | None, _previous=None) -> None:
        if current is None:
            return
        self._current_chapter = str(current.data(0, Qt.ItemDataRole.UserRole))
        self._populate_change_table(self._current_chapter)

    def _populate_change_table(self, chapter_title: str) -> None:
        self._updating = True
        changes = self.changes_by_chapter.get(chapter_title, [])
        self.change_table.setRowCount(len(changes))
        for row, change in enumerate(changes):
            check = QTableWidgetItem()
            check.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            check.setCheckState(
                Qt.CheckState.Checked
                if self.accepted[chapter_title].get(change.index, True)
                else Qt.CheckState.Unchecked
            )
            check.setData(Qt.ItemDataRole.UserRole, change.index)
            self.change_table.setItem(row, 0, check)

            values = [
                _CATEGORY_LABELS.get(change.category, change.category),
                _CONFIDENCE_LABELS.get(change.confidence, change.confidence),
                _display_change_text(change.original, empty="（原为空）"),
                _display_change_text(change.replacement, empty="（删除）"),
                change.reason,
            ]
            tooltip = self._change_tooltip(change)
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                self.change_table.setItem(row, column, item)
        self._updating = False
        self._refresh_preview(chapter_title)

    def _change_checked(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != 0 or not self._current_chapter:
            return
        change_index = int(item.data(Qt.ItemDataRole.UserRole))
        self.accepted[self._current_chapter][change_index] = (
            item.checkState() == Qt.CheckState.Checked
        )
        self._refresh_preview(self._current_chapter)

    def _set_all_checked(self, checked: bool) -> None:
        if not self._current_chapter:
            return
        for change in self.changes_by_chapter.get(self._current_chapter, []):
            self.accepted[self._current_chapter][change.index] = checked
        self._populate_change_table(self._current_chapter)

    def _refresh_preview(self, chapter_title: str) -> None:
        chapter = next(
            (item for item in self.result.chapters if item.title == chapter_title),
            None,
        )
        if chapter is None:
            return
        changes = self.changes_by_chapter.get(chapter_title, [])
        reviewed = apply_review_decisions(
            chapter.original_text,
            changes,
            self.accepted.get(chapter_title, {}),
        )
        diff = difflib.HtmlDiff(wrapcolumn=90).make_table(
            chapter.original_text.splitlines(),
            reviewed.splitlines(),
            fromdesc="修改前",
            todesc="审核后",
            context=True,
            numlines=3,
        )
        self.preview.setHtml(
            "<style>"
            "table.diff { font-family: Consolas, 'Microsoft YaHei UI'; font-size: 12px; width: 100%; }"
            ".diff_header { background: #eef2f8; color: #42516d; }"
            ".diff_next { background: #f8fafc; }"
            "td.diff_add { background: #ddf5e4; }"
            "td.diff_chg { background: #fff0c7; }"
            "td.diff_sub { background: #ffe0e0; }"
            "</style>"
            + diff
        )

    def _apply(self) -> None:
        try:
            paths = write_reviewed_output(self.result, self.accepted)
        except Exception as exc:
            QMessageBox.critical(self, "应用失败", str(exc))
            return
        QMessageBox.information(
            self,
            "审核结果已应用",
            "已重新生成清洗版章节和合并 TXT：\n"
            f"{paths['combined']}\n\n"
            f"审核记录：{paths['decisions']}",
        )
        self._load_changes()

    def _add_selected_to_blacklist(self) -> None:
        selected = self.preview.textCursor().selectedText().strip()
        dialog = AdBlacklistDialog(self, initial_text=selected)
        dialog.exec()

    def _open_reports(self) -> None:
        reports = self.result.reports_dir or self.result.book_dir / "reports"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(reports)))

    def _show_chapter_tooltip(self, item: QTreeWidgetItem, _column: int) -> None:
        QToolTip.showText(QCursor.pos(), item.toolTip(0), self.chapter_tree)

    def _show_cell_tooltip(self, row: int, _column: int) -> None:
        check_item = self.change_table.item(row, 0)
        if check_item is None:
            return
        change_index = int(check_item.data(Qt.ItemDataRole.UserRole))
        change = next(
            (
                item
                for item in self.changes_by_chapter.get(self._current_chapter, [])
                if item.index == change_index
            ),
            None,
        )
        if change is not None:
            QToolTip.showText(QCursor.pos(), self._change_tooltip(change), self.change_table)

    @staticmethod
    def _chapter_tooltip(
        title: str,
        changes: list[DiffChange],
        issues: list[TextIssue],
    ) -> str:
        if not issues:
            return f"<html><body><b>{escape(title)}</b><br>没有自动修改</body></html>"
        counts: dict[str, int] = {}
        for issue in issues:
            counts[issue.category] = counts.get(issue.category, 0) + 1
        count_text = "　".join(
            f"{escape(_CATEGORY_LABELS.get(category, category))} {count}"
            for category, count in counts.items()
        )
        rows = [
            "<html><body style='min-width:360px; max-width:620px;'>",
            f"<div style='font-size:15px; font-weight:700;'>{escape(title)}</div>",
            f"<div style='color:#3f5f9f; margin:5px 0;'>自动修改 {len(issues)} 处　{count_text}</div>",
            "<hr>",
        ]
        for issue in issues[:8]:
            category = escape(_CATEGORY_LABELS.get(issue.category, issue.category))
            original = escape(_short(issue.original, 100))
            replacement = escape(_short(issue.replacement, 100) or "删除")
            reason = escape(issue.reason)
            rows.append(
                "<div style='margin-bottom:8px;'>"
                f"<b>{category}</b>　<span style='color:#7b879b;'>{escape(issue.confidence.value)}</span><br>"
                f"<span style='color:#a33;'>{original}</span> → "
                f"<span style='color:#187b45;'>{replacement}</span><br>"
                f"<span style='color:#60708c;'>{reason}</span></div>"
            )
        if len(issues) > 8:
            rows.append(f"<div>……另有 {len(issues) - 8} 处修改</div>")
        rows.append("</body></html>")
        return "".join(rows)

    @staticmethod
    def _change_tooltip(change: DiffChange) -> str:
        category = escape(_CATEGORY_LABELS.get(change.category, change.category))
        confidence = escape(_CONFIDENCE_LABELS.get(change.confidence, change.confidence))
        original = escape(_short(change.original, 400))
        replacement = escape(_short(change.replacement, 400) or "（删除）")
        return (
            "<html><body style='min-width:380px; max-width:680px;'>"
            f"<div style='font-weight:700;'>{category}　置信度：{confidence}</div>"
            "<hr>"
            "<div><b>问题/原文</b></div>"
            f"<div style='white-space:pre-wrap; color:#a33; margin-bottom:8px;'>{original}</div>"
            "<div><b>修改后</b></div>"
            f"<div style='white-space:pre-wrap; color:#187b45; margin-bottom:8px;'>{replacement}</div>"
            f"<div><b>原因</b></div><div style='color:#60708c;'>{escape(change.reason)}</div>"
            f"<div style='color:#7b879b; margin-top:6px;'>规则：{escape(change.rule)}</div>"
            "</body></html>"
        )


def _short(value: str, length: int) -> str:
    value = value.replace("\n", "\\n")
    return value if len(value) <= length else value[: length - 1] + "…"


def _display_change_text(value: str, *, empty: str) -> str:
    return _short(value, 180) if value else empty

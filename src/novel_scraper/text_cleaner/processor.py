from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from ..utils import safe_atomic_write_text, safe_filename
from .blacklist import AdBlacklistStore
from .cleaner import ChapterCleaner
from .models import BookCleanResult, CleanProgress, CleaningMode
from .report import write_reports
from .rules import CleanerRules, load_rules
from .typo import TextStyleProfile

_CHAPTER_FILE = re.compile(r"^(\d+)[_-](.+)$")


class BookCleaner:
    def __init__(
        self,
        *,
        rules: CleanerRules | None = None,
        user_config_dir: Path | None = None,
        blacklist_store: AdBlacklistStore | None = None,
    ) -> None:
        self.rules = rules or load_rules(user_config_dir)
        self.blacklist_store = blacklist_store or AdBlacklistStore()
        self.chapter_cleaner = ChapterCleaner(
            self.rules,
            self.blacklist_store.load(),
        )

    def process(
        self,
        book_dir: Path,
        mode: CleaningMode = CleaningMode.DETECT,
        *,
        progress_callback: Callable[[CleanProgress], None] | None = None,
    ) -> BookCleanResult:
        book_dir = book_dir.expanduser().resolve()
        chapter_dir = book_dir / "chapters"
        if not chapter_dir.is_dir():
            raise FileNotFoundError(f"未找到章节目录：{chapter_dir}")

        chapter_files = sorted(
            (item for item in chapter_dir.glob("*.txt") if item.is_file()),
            key=_chapter_sort_key,
        )
        if not chapter_files:
            raise FileNotFoundError(f"章节目录中没有 TXT 文件：{chapter_dir}")

        texts = [path.read_text(encoding="utf-8") for path in chapter_files]
        profile = TextStyleProfile.build(texts, self.rules.traditional_map)
        chapter_results = []
        issue_counts: Counter[str] = Counter()
        applied_count = 0

        for index, (path, text) in enumerate(zip(chapter_files, texts), start=1):
            title = _chapter_title(path)
            if progress_callback is not None:
                progress_callback(
                    CleanProgress(
                        current=index - 1,
                        total=len(chapter_files),
                        chapter=title,
                        message="正在检测",
                    )
                )
            result = self.chapter_cleaner.clean_chapter(
                title,
                path,
                text,
                mode,
                profile,
            )
            chapter_results.append(result)
            applied_count += result.applied_count
            issue_counts.update(issue.category for issue in result.issues)
            if progress_callback is not None:
                progress_callback(
                    CleanProgress(
                        current=index,
                        total=len(chapter_files),
                        chapter=title,
                        message="完成",
                    )
                )

        output_dir = None
        cleaned_book_path = None
        if mode == CleaningMode.AUTO:
            output_dir = book_dir / "cleaned"
            cleaned_chapter_dir = output_dir / "chapters"
            cleaned_chapter_dir.mkdir(parents=True, exist_ok=True)
            for result in chapter_results:
                safe_atomic_write_text(
                    cleaned_chapter_dir / result.source_path.name,
                    result.cleaned_text.strip() + "\n",
                )
            cleaned_book_path = _write_cleaned_book(book_dir, output_dir, chapter_results)

        result = BookCleanResult(
            book_dir=book_dir,
            mode=mode,
            chapter_count=len(chapter_results),
            chapters=chapter_results,
            output_dir=output_dir,
            reports_dir=book_dir / "reports",
            cleaned_book_path=cleaned_book_path,
            issue_counts=dict(issue_counts),
            applied_count=applied_count,
        )
        write_reports(result, result.reports_dir or book_dir / "reports")
        return result


def _chapter_sort_key(path: Path) -> tuple[int, str]:
    match = _CHAPTER_FILE.match(path.stem)
    if match:
        return int(match.group(1)), path.name
    return 10**9, path.name


def _chapter_title(path: Path) -> str:
    match = _CHAPTER_FILE.match(path.stem)
    return match.group(2) if match else path.stem


def _write_cleaned_book(
    book_dir: Path,
    output_dir: Path,
    chapters: list,
) -> Path:
    lines = [
        f"{book_dir.name}（保守清洗版）",
        f"来源目录：{book_dir}",
        "",
    ]
    for chapter in chapters:
        lines.extend([chapter.title, "", chapter.cleaned_text.strip(), ""])
    path = output_dir / f"{safe_filename(book_dir.name, fallback='novel')}_清洗版.txt"
    return safe_atomic_write_text(path, "\n".join(lines).rstrip() + "\n")

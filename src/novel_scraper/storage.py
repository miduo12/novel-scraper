from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .models import Book, Chapter
from .utils import atomic_write_text, safe_filename

STATE_VERSION = 1


@dataclass(slots=True)
class StoredState:
    completed: set[str] = field(default_factory=set)
    failures: dict[str, dict[str, str]] = field(default_factory=dict)
    duplicates: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: object) -> StoredState:
        if not isinstance(payload, dict):
            return cls()
        completed = payload.get("completed", [])
        failures = payload.get("failures", {})
        duplicates = payload.get("duplicates", {})
        return cls(
            completed={str(item) for item in completed} if isinstance(completed, list) else set(),
            failures=failures if isinstance(failures, dict) else {},
            duplicates=duplicates if isinstance(duplicates, dict) else {},
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "version": STATE_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "completed": sorted(self.completed),
            "failures": self.failures,
            "duplicates": self.duplicates,
        }


class BookStorage:
    def __init__(self, output_root: Path, book: Book) -> None:
        self.book = book
        self.root = output_root / safe_filename(book.title, fallback="novel")
        self.chapters_dir = self.root / "chapters"
        self.state_path = self.root / "state.json"
        self.failures_path = self.root / "failed_chapters.txt"
        self.duplicates_path = self.root / "duplicate_chapters.txt"
        self.combined_path = self.root / f"{safe_filename(book.title, fallback='novel')}.txt"
        self.chapters_dir.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> StoredState:
        if not self.state_path.exists():
            return StoredState()
        try:
            return StoredState.from_payload(json.loads(self.state_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            return StoredState()

    def save_state(self, state: StoredState) -> None:
        atomic_write_text(
            self.state_path,
            json.dumps(state.to_payload(), ensure_ascii=False, indent=2) + "\n",
        )

    def chapter_path(self, chapter: Chapter) -> Path:
        filename = f"{chapter.index:04d}_{safe_filename(chapter.title, fallback='chapter')}.txt"
        return self.chapters_dir / filename

    def save_chapter(self, chapter: Chapter, content: str) -> Path:
        path = self.chapter_path(chapter)
        atomic_write_text(path, content.strip() + "\n")
        return path

    def mark_completed(self, state: StoredState, chapter: Chapter) -> None:
        state.completed.add(chapter.url)
        state.failures.pop(chapter.url, None)
        self.save_state(state)

    def mark_failed(self, state: StoredState, chapter: Chapter, reason: str) -> None:
        state.completed.discard(chapter.url)
        state.failures[chapter.url] = {"title": chapter.title, "reason": reason}
        self.save_state(state)

    def mark_duplicate(
        self,
        state: StoredState,
        chapter: Chapter,
        digest: str,
        first_title: str,
        first_url: str,
    ) -> None:
        state.duplicates[chapter.url] = {
            "title": chapter.title,
            "hash": digest,
            "first_title": first_title,
            "first_url": first_url,
        }
        self.save_state(state)

    def write_duplicates(self, state: StoredState) -> Path | None:
        if not state.duplicates:
            if self.duplicates_path.exists():
                self.duplicates_path.unlink()
            return None
        blocks = ["重复章节记录", ""]
        for chapter in self.book.chapters:
            duplicate = state.duplicates.get(chapter.url)
            if not duplicate:
                continue
            blocks.extend(
                [
                    chapter.title,
                    chapter.url,
                    f"首次出现：{duplicate.get('first_title', '未知')}",
                    f"首次地址：{duplicate.get('first_url', '')}",
                    f"正文哈希：{duplicate.get('hash', '')}",
                    "",
                ]
            )
        atomic_write_text(self.duplicates_path, "\n".join(blocks).rstrip() + "\n")
        return self.duplicates_path

    def write_failures(self, state: StoredState) -> Path | None:
        if not state.failures:
            if self.failures_path.exists():
                self.failures_path.unlink()
            return None
        blocks = ["失败章节记录", ""]
        for chapter in self.book.chapters:
            failure = state.failures.get(chapter.url)
            if not failure:
                continue
            blocks.extend(
                [
                    failure.get("title", chapter.title),
                    chapter.url,
                    f"失败原因：{failure.get('reason', '未知错误')}",
                    "",
                ]
            )
        atomic_write_text(self.failures_path, "\n".join(blocks).rstrip() + "\n")
        return self.failures_path

    def build_combined_txt(self) -> Path:
        blocks = [
            self.book.title,
            f"作者：{self.book.author or '未知'}",
            f"来源：{self.book.source_url}",
            "",
        ]
        for chapter in self.book.chapters:
            path = self.chapter_path(chapter)
            if not path.exists():
                continue
            body = path.read_text(encoding="utf-8").strip()
            blocks.extend([chapter.title, "", body, ""])
        atomic_write_text(self.combined_path, "\n".join(blocks).rstrip() + "\n")
        return self.combined_path

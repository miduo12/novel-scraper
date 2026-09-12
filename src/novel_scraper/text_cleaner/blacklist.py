from __future__ import annotations

import difflib
import html
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..utils import atomic_write_text

_SPACE_OR_PUNCTUATION = re.compile(r"[\W_]+", re.UNICODE)
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


def default_blacklist_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "NovelScraper" / "ad_blacklist.json"
    return Path.home() / ".config" / "novel_scraper" / "ad_blacklist.json"


def normalize_match_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return _SPACE_OR_PUNCTUATION.sub("", text).lower()


def _ngrams(text: str, size: int = 3) -> set[str]:
    if len(text) < size:
        return {text} if text else set()
    return {text[index : index + size] for index in range(len(text) - size + 1)}


@dataclass(frozen=True, slots=True)
class AdBlacklistEntry:
    id: str
    text: str
    created_at: str

    @classmethod
    def from_payload(cls, payload: object) -> "AdBlacklistEntry | None":
        if not isinstance(payload, dict):
            return None
        entry_id = str(payload.get("id", "")).strip()
        text = str(payload.get("text", "")).strip()
        if not entry_id or not text:
            return None
        return cls(
            id=entry_id,
            text=text,
            created_at=str(payload.get("created_at", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text, "created_at": self.created_at}


@dataclass(frozen=True, slots=True)
class BlacklistMatch:
    entry: AdBlacklistEntry
    score: float
    method: str


class AdBlacklistStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_blacklist_path()
        self._lock = threading.Lock()

    def load(self) -> list[AdBlacklistEntry]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw_entries = payload.get("entries", []) if isinstance(payload, dict) else []
        entries = [AdBlacklistEntry.from_payload(item) for item in raw_entries]
        return [entry for entry in entries if entry is not None]

    def add(self, text: str) -> AdBlacklistEntry:
        text = text.strip()
        normalized = normalize_match_text(text)
        if len(normalized) < 6:
            raise ValueError("广告黑名单内容至少需要 6 个有效字符")
        with self._lock:
            entries = self.load()
            for entry in entries:
                if normalize_match_text(entry.text) == normalized:
                    return entry
            digest = __import__("hashlib").sha256(normalized.encode("utf-8")).hexdigest()[:16]
            entry = AdBlacklistEntry(
                id=digest,
                text=text,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            entries.append(entry)
            self._save(entries)
            return entry

    def remove(self, entry_id: str) -> bool:
        with self._lock:
            entries = self.load()
            filtered = [entry for entry in entries if entry.id != entry_id]
            if len(filtered) == len(entries):
                return False
            self._save(filtered)
            return True

    def _save(self, entries: list[AdBlacklistEntry]) -> None:
        payload = {
            "version": 1,
            "entries": [entry.to_dict() for entry in entries],
        }
        atomic_write_text(
            self.path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )


def find_blacklist_match(
    paragraph: str,
    entries: list[AdBlacklistEntry],
    *,
    high_threshold: float = 0.88,
) -> BlacklistMatch | None:
    paragraph_normalized = normalize_match_text(paragraph)
    if len(paragraph_normalized) < 6:
        return None

    best: BlacklistMatch | None = None
    for entry in entries:
        entry_normalized = normalize_match_text(entry.text)
        if len(entry_normalized) < 6:
            continue
        if entry_normalized in paragraph_normalized:
            score = 1.0
            method = "contains"
        elif paragraph_normalized in entry_normalized and len(paragraph_normalized) >= len(entry_normalized) * 0.65:
            score = len(paragraph_normalized) / len(entry_normalized)
            method = "contained"
        else:
            if min(len(paragraph_normalized), len(entry_normalized)) < 10:
                continue
            length_ratio = min(len(paragraph_normalized), len(entry_normalized)) / max(
                len(paragraph_normalized), len(entry_normalized)
            )
            if length_ratio < 0.35:
                continue
            sequence_score = difflib.SequenceMatcher(
                None,
                paragraph_normalized,
                entry_normalized,
                autojunk=False,
            ).ratio()
            paragraph_grams = _ngrams(paragraph_normalized)
            entry_grams = _ngrams(entry_normalized)
            union = paragraph_grams | entry_grams
            dice = (
                2 * len(paragraph_grams & entry_grams) / (len(paragraph_grams) + len(entry_grams))
                if paragraph_grams and entry_grams
                else 0.0
            )
            score = max(sequence_score, dice)
            method = "fuzzy"

        if best is None or score > best.score:
            best = BlacklistMatch(entry=entry, score=score, method=method)

    if best is not None and best.score >= 0.78:
        return best
    return None

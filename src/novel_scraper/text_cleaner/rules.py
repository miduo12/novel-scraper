from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


def packaged_config_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return base / "novel_scraper" / "resources" / "config"
    return Path(__file__).resolve().parents[1] / "resources" / "config"


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


@dataclass(slots=True)
class CleanerRules:
    ad_rules: dict[str, object] = field(default_factory=dict)
    whitelist: list[str] = field(default_factory=list)
    traditional_map: dict[str, str] = field(default_factory=dict)

    @property
    def url_pattern(self) -> str:
        return str(self.ad_rules.get("url_pattern", ""))

    @property
    def domain_pattern(self) -> str:
        return str(self.ad_rules.get("domain_pattern", ""))

    @property
    def strong_phrases(self) -> list[str]:
        value = self.ad_rules.get("strong_phrases", [])
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def promo_cues(self) -> list[str]:
        value = self.ad_rules.get("promo_cues", [])
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def soft_cues(self) -> list[str]:
        value = self.ad_rules.get("soft_cues", [])
        return [str(item) for item in value] if isinstance(value, list) else []


def load_rules(user_config_dir: Path | None = None) -> CleanerRules:
    base_dir = packaged_config_dir()
    ad_rules = _read_json(base_dir / "ad_rules.json")
    whitelist_payload = _read_json(base_dir / "whitelist.json")
    traditional_map = _read_json(base_dir / "traditional_map.json")

    if user_config_dir is not None:
        ad_rules = _merge(ad_rules, _read_json(user_config_dir / "ad_rules.json"))
        whitelist_payload = _merge(
            whitelist_payload,
            _read_json(user_config_dir / "whitelist.json"),
        )
        traditional_map = _merge(
            traditional_map,
            _read_json(user_config_dir / "traditional_map.json"),
        )

    raw_whitelist = whitelist_payload.get("terms", [])
    whitelist = [str(item) for item in raw_whitelist] if isinstance(raw_whitelist, list) else []
    normalized_map = {
        str(key): str(value)
        for key, value in traditional_map.items()
        if isinstance(key, str) and isinstance(value, str) and len(key) == 1 and len(value) == 1
    }
    return CleanerRules(
        ad_rules=ad_rules,
        whitelist=whitelist,
        traditional_map=normalized_map,
    )

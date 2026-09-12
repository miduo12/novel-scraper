from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .models import BookCleanResult
from ..utils import atomic_write_text


def write_reports(result: BookCleanResult, reports_dir: Path) -> dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": reports_dir / "clean_report.json",
        "csv": reports_dir / "clean_report.csv",
        "log": reports_dir / "clean_log.json",
        "text": reports_dir / "clean_report.txt",
    }

    chapters_payload = []
    applied_issues = []
    confidence_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()

    for chapter in result.chapters:
        chapter_issues = []
        for issue in chapter.issues:
            payload = issue.to_dict()
            chapter_issues.append(payload)
            confidence_counts[issue.confidence.value] += 1
            category_counts[issue.category] += 1
            if issue.applied:
                applied_issues.append(payload)
        chapters_payload.append(
            {
                "title": chapter.title,
                "source_path": str(chapter.source_path),
                "changed": chapter.cleaned_text != chapter.original_text,
                "applied_count": chapter.applied_count,
                "issues": chapter_issues,
            }
        )

    summary = {
        "chapter_count": result.chapter_count,
        "total_issues": result.total_issues,
        "applied_count": result.applied_count,
        "categories": dict(category_counts),
        "confidence": dict(confidence_counts),
        "mode": result.mode.value,
        "book_dir": str(result.book_dir),
        "cleaned_book_path": str(result.cleaned_book_path) if result.cleaned_book_path else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    json_payload = {"summary": summary, "chapters": chapters_payload}
    atomic_write_text(
        paths["json"],
        json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write_text(
        paths["log"],
        json.dumps(
            {
                "summary": summary,
                "applied_changes": applied_issues,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "chapter",
            "category",
            "confidence",
            "confidence_score",
            "rule",
            "reason",
            "original",
            "replacement",
            "action",
            "applied",
            "paragraph",
        ],
    )
    writer.writeheader()
    for chapter in result.chapters:
        for issue in chapter.issues:
            writer.writerow(issue.to_dict())
    atomic_write_text(paths["csv"], output.getvalue())
    paths["csv"].write_text(output.getvalue(), encoding="utf-8-sig", newline="")

    lines = [
        "小说内容检测报告",
        "=" * 24,
        f"处理模式：{result.mode.value}",
        f"章节数量：{result.chapter_count}",
        f"问题总数：{result.total_issues}",
        f"自动修改：{result.applied_count}",
        "",
        "分类统计：",
    ]
    for category, count in sorted(category_counts.items()):
        lines.append(f"  {category}: {count}")
    lines.extend(["", "置信度统计："])
    for confidence, count in sorted(confidence_counts.items()):
        lines.append(f"  {confidence}: {count}")
    if result.cleaned_book_path:
        lines.extend(["", f"清洗版 TXT：{result.cleaned_book_path}"])
    atomic_write_text(paths["text"], "\n".join(lines) + "\n")
    return paths

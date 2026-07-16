"""CCC lessons pipeline — 记录失败教训供 product 角色参考 (v0.31)"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _lessons_dir(ws_path: Path) -> Path:
    d = ws_path / ".ccc" / "lessons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def record_failure(
    ws_path: Path, task_id: str, phase: str | int, error: str, analysis: str = ""
) -> dict:
    """记录一次任务失败到 .ccc/lessons/{task_id}.json"""
    record = {
        "task_id": task_id,
        "phase": phase,
        "error": error,
        "analysis": analysis,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "fixed": False,
    }
    out = _lessons_dir(ws_path) / f"{task_id}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def get_recent_lessons(ws_path: Path, count: int = 50) -> list[dict]:
    """读取 .ccc/lessons/ 下所有 json，按 timestamp 排序，返回最近 count 条。"""
    lessons_dir = ws_path / ".ccc" / "lessons"
    if not lessons_dir.is_dir():
        return []
    items: list[dict] = []
    for fp in lessons_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text())
            if isinstance(data, dict):
                items.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return items[:count]


def mark_fixed(ws_path: Path, task_id: str) -> bool:
    """标记某条教训已修复（fixed: true）。"""
    fp = ws_path / ".ccc" / "lessons" / f"{task_id}.json"
    if not fp.exists():
        return False
    try:
        data = json.loads(fp.read_text())
        data["fixed"] = True
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return True
    except (json.JSONDecodeError, OSError):
        return False


# v0.32: 扫描 docs/lessons.md 中所有 `## Lesson N` 标题，仅行首匹配（避免正文误命中）。
_LESSON_HEADING_RE = re.compile(r"^## Lesson (\d+)")


def _next_lesson_number(ws_path: Path) -> int:
    """扫描 docs/lessons.md 找到最新 Lesson 编号，返回下一个。

    没有匹配到任何 Lesson 时返回 1。
    """
    lessons_md = ws_path / "docs" / "lessons.md"
    if not lessons_md.exists():
        return 1
    max_n = 0
    for line in lessons_md.read_text().split("\n"):
        m = _LESSON_HEADING_RE.match(line.strip())
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return max_n + 1


def auto_append_lesson_md(
    ws_path: Path,
    task_id: str,
    phase: int | str | None,
    error: str,
) -> None:
    """自动追加一条 Lesson 记录到 docs/lessons.md。

    格式对标已有 Lesson 结构（标题 + 元信息 + 自检提示），
    内容完全由调用方提供（不分析根因或修复方案）。
    """
    lessons_md = ws_path / "docs" / "lessons.md"
    n = _next_lesson_number(ws_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    phase_str = str(phase) if phase is not None else "N/A"
    entry = (
        "\n---\n"
        f"\n## Lesson {n}：{task_id} 进入异常状态\n"
        f"\n**项目**：`{ws_path}` | **Phase**：{phase_str} | **时间**：{timestamp}\n"
        f"\n**失败原因**：{error}\n"
        f"\n**待分析**：由 product_role 后续补充根因和修复方案\n"
    )
    with open(lessons_md, "a", encoding="utf-8") as f:
        f.write(entry)

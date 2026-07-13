"""CCC lessons pipeline — 记录失败教训供 product 角色参考 (v0.31)"""

from __future__ import annotations

import json
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


def get_recent_lessons(ws_path: Path, count: int = 30) -> list[dict]:
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

"""活跃板计数过滤：与 Board API / FileBoardStore 同口径。

跳过 ui_hidden=true 与 epic split_status=done；failed 仍计入活跃风险。
契约：docs/product/loop-engineer-authority.md · 活跃板计数与 ready
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_task_head(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        line = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not line:
            return None
        data = json.loads(line[0])
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, IndexError):
        return None


def is_active_board_task(data: dict[str, Any] | None) -> bool:
    """Whether this card should count in active lens/baseline/mind board counts."""
    if not data:
        return True  # unreadable → keep visible (fail-safe)
    if bool(data.get("ui_hidden")):
        return False
    kind = str(data.get("card_kind") or "").strip().lower()
    split = str(data.get("split_status") or "").strip().lower()
    if kind == "epic" and split == "done":
        return False
    # aliases
    if kind == "epic" and split in ("complete", "completed"):
        return False
    return True


def iter_active_jsonl(col_dir: Path) -> list[Path]:
    if not col_dir.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(col_dir.glob("*.jsonl")):
        if not p.is_file():
            continue
        if is_active_board_task(load_task_head(p)):
            out.append(p)
    return out

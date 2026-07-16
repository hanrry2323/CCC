"""_failure_ledger.py — CCC 统一失败账本（v0.40）

SSOT 路径：<workspace>/.ccc/stats/failures.jsonl（append-only）

主写入点：quarantine / product_fail / hang / role exit≠0
运维：python3 scripts/ccc-failure-report.py --last 20
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_log = logging.getLogger("ccc.failures")

_MAX_TAIL_CHARS = 2048
_MAX_TAIL_LINES = 20


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def failures_path(workspace: Path) -> Path:
    return Path(workspace) / ".ccc" / "stats" / "failures.jsonl"


def _read_tail(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _log.exception("read stderr_path failed: %s", path)
        return f"<read error: {exc}>"
    lines = text.splitlines()
    tail = "\n".join(lines[-_MAX_TAIL_LINES:])
    if len(tail) > _MAX_TAIL_CHARS:
        return tail[-_MAX_TAIL_CHARS:]
    return tail


def resolve_stderr_path(workspace: Path, task_id: str) -> Optional[str]:
    """优先 reports/<tid>.result.json，否则 verdict。"""
    ws = Path(workspace)
    for rel in (
        f".ccc/reports/{task_id}.result.json",
        f".ccc/verdicts/{task_id}.verdict.md",
        f".ccc/reports/{task_id}.report.md",
    ):
        p = ws / rel
        if p.is_file():
            return rel
    return None


def record_failure(
    workspace: Path,
    *,
    task_id: str,
    role: str,
    reason: str,
    phase: int | None = None,
    from_col: str | None = None,
    to_col: str | None = "abnormal",
    exit_code: int | None = None,
    stderr_path: str | None = None,
    related_stats_event: str = "quarantine",
    extra: dict[str, Any] | None = None,
) -> Path:
    """Append one failure row. Raises on write failure (caller must not swallow silently)."""
    ws = Path(workspace)
    out = failures_path(ws)
    out.parent.mkdir(parents=True, exist_ok=True)

    rel_stderr = stderr_path or resolve_stderr_path(ws, task_id)
    abs_stderr = (ws / rel_stderr) if rel_stderr else None
    tail = _read_tail(abs_stderr) if abs_stderr else ""

    row: dict[str, Any] = {
        "ts": _now_iso(),
        "task_id": task_id,
        "workspace": ws.name,
        "role": role,
        "phase": phase,
        "from_col": from_col,
        "to_col": to_col,
        "exit_code": exit_code,
        "reason": (reason or "")[:500],
        "stderr_path": rel_stderr,
        "stderr_tail": tail,
        "related_stats_event": related_stats_event,
    }
    if extra:
        row["extra"] = extra

    line = json.dumps(row, ensure_ascii=False) + "\n"
    with out.open("a", encoding="utf-8") as f:
        f.write(line)
    return out


def read_failures(workspace: Path, *, last: int = 20) -> list[dict[str, Any]]:
    path = failures_path(workspace)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        _log.exception("read failures.jsonl failed: %s", path)
        return []
    if last <= 0:
        return rows
    return rows[-last:]


def infer_role_from_reason(reason: str) -> str:
    r = (reason or "").lower()
    if "product" in r:
        return "product"
    if "reviewer" in r or "verdict" in r or "fallback" in r:
        return "reviewer"
    if "tester" in r or "pytest" in r:
        return "tester"
    if "hang" in r or "watchdog" in r:
        return "engine"
    if "opencode" in r or "dev_role" in r or "phase" in r:
        return "dev"
    if "kb" in r:
        return "kb"
    return "engine"

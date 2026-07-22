"""ccc_hygiene — ops/卫生卡判定（跳过强制全仓 pytest、识别 .ccc-only scope）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_phase_scopes(ws: Path, tid: str) -> list[str]:
    pf = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if not pf.is_file():
        return []
    scopes: list[str] = []
    for line in pf.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict) or "phase" not in d:
            continue
        sc = d.get("scope") or []
        if isinstance(sc, list):
            scopes.extend(str(x).strip() for x in sc if str(x).strip())
    return scopes


def scopes_are_ccc_only(scopes: list[str]) -> bool:
    """全部 scope 落在 .ccc/ 下（编排产物卫生）。"""
    if not scopes:
        return False
    for s in scopes:
        p = str(s).strip()
        while p.startswith("./"):
            p = p[2:]
        if p in (".ccc", "state.md", "index.json"):
            continue
        if not (p == ".ccc" or p.startswith(".ccc/")):
            return False
    return True


def _pipeline_from_task(task: dict[str, Any] | None) -> str:
    if not task:
        return ""
    note = task.get("note") or ""
    if isinstance(note, str) and note.strip().startswith("{"):
        try:
            meta = json.loads(note)
            gate = meta.get("transfer_gate") or {}
            if isinstance(gate, dict):
                return str(gate.get("pipeline") or "").strip().lower()
        except json.JSONDecodeError:
            pass
    desc = str(task.get("description") or "")
    for line in desc.splitlines():
        low = line.strip().lower()
        if low.startswith("- pipeline:"):
            return low.split(":", 1)[-1].strip()
    tags = task.get("tags") or []
    for t in tags:
        ts = str(t).lower()
        if ts in ("ops", "hygiene", "board_ops", "ccc-hygiene"):
            return ts
    return ""


def task_skips_forced_pytest(
    ws: Path, tid: str, task: dict[str, Any] | None = None
) -> bool:
    """ops/卫生 / .ccc-only scope：禁止 engine/tester 强制全仓 pytest。"""
    pipeline = _pipeline_from_task(task)
    if pipeline in ("ops", "hygiene", "board", "board_ops"):
        return True
    if task:
        tags = {str(t).lower() for t in (task.get("tags") or [])}
        if tags & {"ops", "hygiene", "ccc-hygiene", "board_ops"}:
            return True
        title = str(task.get("title") or "").lower()
        if any(k in title for k in ("卫生", "清场", "编排产物", "hygiene")):
            return True
    scopes = _load_phase_scopes(ws, tid)
    return scopes_are_ccc_only(scopes)

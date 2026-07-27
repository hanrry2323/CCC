"""ccc_hygiene — ops/卫生卡判定（跳过强制全仓 pytest、识别 .ccc-only scope）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _logger import get_logger

_log = get_logger("ccc_hygiene")


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


def _hygiene_is_board_ops(task: dict[str, Any] | None) -> bool:
    """True only for explicit board_ops/ops/hygiene pipeline — NOT doc_only/docs scope.

    Used by ensure_task_commit to decide whether .ccc meta may be auto-committed.
    pipeline/tags only — intentionally narrower than task_skips_forced_pytest.
    """
    pipeline = _pipeline_from_task(task)
    if pipeline in ("ops", "hygiene", "board", "board_ops"):
        return True
    if task:
        tags = {str(t).lower() for t in (task.get("tags") or [])}
        if tags & {"ops", "hygiene", "ccc-hygiene", "board_ops"}:
            return True
    return False


def scopes_are_docs_only(scopes: list[str]) -> bool:
    """全部 scope 落在 docs/ 或纯 markdown 报告戳记（禁止强制全仓 pytest）。"""
    if not scopes:
        return False
    for s in scopes:
        p = str(s).strip().replace("\\", "/")
        while p.startswith("./"):
            p = p[2:]
        if not p:
            return False
        if p.startswith("docs/") or p.endswith(".md"):
            continue
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
        except json.JSONDecodeError as e:
            _log.debug("hygiene phases parse: %s", e)
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
    """ops/卫生 / .ccc-only / docs-only scope：禁止 engine/tester 强制全仓 pytest。"""
    pipeline = _pipeline_from_task(task)
    if pipeline in ("ops", "hygiene", "board", "board_ops"):
        return True
    if task:
        tags = {str(t).lower() for t in (task.get("tags") or [])}
        if tags & {"ops", "hygiene", "ccc-hygiene", "board_ops", "doc_only", "no-pytest"}:
            return True
        title = str(task.get("title") or "").lower()
        if any(k in title for k in ("卫生", "清场", "编排产物", "hygiene", "文档戳记")):
            return True
    # result.json path=doc_only（短路径审测）
    rp = Path(ws) / ".ccc" / "reports" / f"{tid}.result.json"
    if rp.is_file():
        try:
            data = json.loads(rp.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict) and str(data.get("path") or "").strip().lower() in (
                "doc_only",
                "script_seed",
                "board_ops",
                "feature_seed",
            ):
                return True
        except (OSError, json.JSONDecodeError) as exc:
            _log.debug("hygiene result.json path probe: %s", exc)
    scopes = _load_phase_scopes(ws, tid)
    if scopes_are_ccc_only(scopes):
        return True
    return scopes_are_docs_only(scopes)

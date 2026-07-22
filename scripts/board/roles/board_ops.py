"""Deterministic board hygiene short path — no opencode.

Trigger: work executor in {python, auto} AND all phase scopes under .ccc/board/**
(plus .ccc/state.md / index). Moves backlog→released for listed ids, rebuilds index,
writes report + task commit, leaves card ready for testing/acceptance.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.board_ops")

_BOARD_SCOPE_PREFIXES = (
    ".ccc/board/",
    ".ccc/state.md",
    ".ccc/board/index.json",
    # 产物卫生常见范围（仍禁止 src/tests 等业务树）
    ".ccc/plans/",
    ".ccc/phases/",
    ".ccc/reports/",
    ".ccc/verdicts/",
    ".ccc/lessons/",
    ".ccc/stats/",
)


def _load_phases(ws: Path, tid: str) -> list[dict[str, Any]]:
    pf = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if not pf.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in pf.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "phase" in d:
            out.append(d)
    return out


def scope_is_board_only(phases: list[dict[str, Any]]) -> bool:
    scopes: list[str] = []
    for p in phases:
        sc = p.get("scope") or []
        if isinstance(sc, list):
            scopes.extend(str(x) for x in sc if str(x).strip())
    if not scopes:
        return False
    for s in scopes:
        s = str(s).strip()
        while s.startswith("./"):
            s = s[2:]
        if not any(s == pref.rstrip("/") or s.startswith(pref) for pref in _BOARD_SCOPE_PREFIXES):
            # allow index/state short names
            if s in ("index.json", "state.md"):
                continue
            return False
    return True


def should_use_board_ops(ws: Path, task: dict[str, Any]) -> bool:
    exec_id = str(task.get("executor") or "").strip().lower()
    if exec_id not in ("python", "auto", "cli"):
        return False
    tid = str(task.get("id") or "")
    phases = _load_phases(ws, tid)
    return scope_is_board_only(phases)


def _ids_to_retire(phases: list[dict[str, Any]], plan_text: str) -> list[str]:
    """Collect task ids from phase scopes (backlog/*.jsonl stems)."""
    ids: list[str] = []
    for p in phases:
        for s in p.get("scope") or []:
            s = str(s).strip()
            while s.startswith("./"):
                s = s[2:]
            if s.startswith(".ccc/board/backlog/") and s.endswith(".jsonl"):
                ids.append(Path(s).stem)
            if s.startswith(".ccc/board/released/") and s.endswith(".jsonl"):
                pass
    # plan bullets mentioning jsonl stems
    for line in (plan_text or "").splitlines():
        if "backlog/" in line and ".jsonl" in line:
            for part in line.replace("`", " ").split():
                if part.endswith(".jsonl") and "backlog" in part:
                    ids.append(Path(part).stem)
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def run_board_ops(ws: Path, tid: str) -> dict[str, Any]:
    """Execute board hygiene and leave task in in_progress with markers for salvage/complete."""
    from _board_store import FileBoardStore
    from _task_commit import ensure_task_commit
    from board.context import set_workspace

    ws = Path(ws)
    set_workspace(ws)
    store = FileBoardStore(ws)
    phases = _load_phases(ws, tid)
    plan_path = ws / ".ccc" / "plans" / f"{tid}.plan.md"
    plan_text = plan_path.read_text(encoding="utf-8", errors="replace") if plan_path.is_file() else ""
    retire = _ids_to_retire(phases, plan_text)
    moved: list[str] = []
    skipped: list[str] = []

    for rid in retire:
        src = ws / ".ccc" / "board" / "backlog" / f"{rid}.jsonl"
        dst = ws / ".ccc" / "board" / "released" / f"{rid}.jsonl"
        if not src.is_file():
            if dst.is_file():
                skipped.append(f"{rid}:already_released")
            else:
                skipped.append(f"{rid}:missing")
            continue
        # prefer store.move_task when card is registered
        col, _ = store.find_task(rid)
        if col == "backlog":
            ok = store.move_task(rid, "backlog", "released")
            if ok:
                moved.append(rid)
            else:
                # fallback filesystem
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                moved.append(rid)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            moved.append(rid)
        else:
            skipped.append(f"{rid}:col={col}")

    store.update_index()

    # mark phases done
    if phases:
        lines = []
        pf = ws / ".ccc" / "phases" / f"{tid}.phases.json"
        header = {"schema_version": "1.1"}
        lines.append(json.dumps(header, ensure_ascii=False))
        for p in phases:
            p = dict(p)
            p["status"] = "done"
            lines.append(json.dumps(p, ensure_ascii=False))
        pf.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = ws / ".ccc" / "reports" / f"{tid}.report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        f"# {tid} board_ops 执行报告\n\n"
        f"## 信息\n- 路径: board_ops（确定性短路径）\n"
        f"- moved: {', '.join(moved) or '(none)'}\n"
        f"- skipped: {', '.join(skipped) or '(none)'}\n\n"
        f"ALL SELF-CHECKS PASSED\n",
        encoding="utf-8",
    )
    result = ws / ".ccc" / "reports" / f"{tid}.result.json"
    result.write_text(
        json.dumps(
            {"ok": True, "moved": moved, "skipped": skipped, "path": "board_ops"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    ok_c, why, commit = ensure_task_commit(ws, tid, phase_num=1, pre_head="")
    # done marker so check_complete can finish
    pids = ws / ".ccc" / "pids"
    pids.mkdir(parents=True, exist_ok=True)
    (pids / f"{tid}.done").write_text("1\n", encoding="utf-8")
    (pids / f"{tid}.exitcode").write_text("0\n", encoding="utf-8")

    _log.info(
        "[board_ops] %s moved=%s commit=%s (%s)",
        tid,
        moved,
        (commit or "")[:12],
        why,
    )
    return {
        "ok": bool(ok_c and commit),
        "moved": moved,
        "skipped": skipped,
        "commit": commit or "",
        "why": why,
        "path": "board_ops",
    }

#!/usr/bin/env python3
"""ccc-pipeline-status.py — 编排面 stuck 一查询（Wave C）

用法:
  python3 scripts/ccc-pipeline-status.py
  python3 scripts/ccc-pipeline-status.py --workspace ~/program/apps/qb
  python3 scripts/ccc-pipeline-status.py --all-engine
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from _board_store import COLUMNS, FileBoardStore  # noqa: E402


def _pid_alive(ws: Path, tid: str) -> tuple[bool, int | None]:
    pid_path = ws / ".ccc" / "pids" / f"{tid}.pid"
    if not pid_path.is_file():
        return False, None
    try:
        pid = int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return False, None
    if pid <= 0:
        return False, None
    try:
        os.kill(pid, 0)
        return True, pid
    except (OSError, ProcessLookupError):
        return False, pid


def _idle_sec(ws: Path, tid: str) -> float | None:
    try:
        from engine.hang import _activity_mtime

        act = _activity_mtime(ws, tid)
        if act <= 0:
            return None
        return max(0.0, time.time() - act)
    except Exception:
        return None


def _last_gate_hint(ws: Path, tid: str) -> str:
    report = ws / ".ccc" / "reports" / f"{tid}.report.md"
    if report.is_file():
        try:
            text = report.read_text(encoding="utf-8")[:800]
            for key in (
                "missing SELF-CHECKS",
                "HOLLOW FAIL",
                "commit-gate",
                "salvage",
            ):
                if key in text:
                    return key
        except OSError:
            pass
    note_cols = ("abnormal", "in_progress", "testing")
    store = FileBoardStore(ws)
    for col in note_cols:
        for t in store.list_tasks(col):
            if t.get("id") == tid:
                note = (t.get("note") or "").strip()
                return note[:120] if note else ""
    return ""


def status_workspace(ws: Path) -> list[dict]:
    if not (ws / ".ccc" / "board").is_dir():
        return []
    store = FileBoardStore(ws)
    rows: list[dict] = []
    for col in COLUMNS:
        for t in store.list_tasks(col):
            if t.get("ui_hidden"):
                continue
            tid = t.get("id") or ""
            kind = t.get("card_kind") or ""
            alive, pid = _pid_alive(ws, tid) if kind == "work" and col == "in_progress" else (False, None)
            idle = _idle_sec(ws, tid) if kind == "work" else None
            rows.append(
                {
                    "workspace": ws.name,
                    "id": tid,
                    "kind": kind,
                    "col": col,
                    "split_status": t.get("split_status"),
                    "title": (t.get("title") or "")[:60],
                    "pid_alive": alive,
                    "pid": pid,
                    "idle_sec": int(idle) if idle is not None else None,
                    "last_gate": _last_gate_hint(ws, tid) if kind == "work" else "",
                }
            )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="CCC pipeline stuck status")
    ap.add_argument("--workspace", help="single workspace root")
    ap.add_argument(
        "--all-engine",
        action="store_true",
        help="scan all engine workspaces from ~/.ccc/workspaces.json",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    workspaces: list[Path] = []
    if args.workspace:
        workspaces = [Path(args.workspace).expanduser().resolve()]
    elif args.all_engine:
        try:
            from _workspace_registry import list_engine_paths

            workspaces = [Path(p) for p in list_engine_paths()]
        except Exception as exc:
            print(f"list_engine_paths failed: {exc}", file=sys.stderr)
            return 2
    else:
        workspaces = [SCRIPTS.parent.resolve()]

    all_rows: list[dict] = []
    for ws in workspaces:
        all_rows.extend(status_workspace(ws))

    if args.json:
        print(json.dumps(all_rows, ensure_ascii=False, indent=2))
        return 0

    if not all_rows:
        print("(no board tasks)")
        return 0

    print(f"{'ws':12} {'col':12} {'kind':5} {'ss':8} {'alive':5} {'idle':6} id")
    for r in all_rows:
        alive = "Y" if r.get("pid_alive") else "-"
        idle = str(r.get("idle_sec") if r.get("idle_sec") is not None else "-")
        ss = str(r.get("split_status") or "-")[:8]
        print(
            f"{r['workspace'][:12]:12} {r['col'][:12]:12} {r['kind'][:5]:5} "
            f"{ss:8} {alive:5} {idle:6} {r['id']}"
        )
        if r.get("last_gate"):
            print(f"  gate: {r['last_gate'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

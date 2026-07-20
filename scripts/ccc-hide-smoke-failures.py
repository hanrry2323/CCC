#!/usr/bin/env python3
"""ccc-hide-smoke-failures.py — Wave D：ui_hidden 历史烟测 failed 卡

只处理 id 前缀 flow-smoke- / flow-green-；done epic 保留可见。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from _board_store import FileBoardStore  # noqa: E402

_PREFIXES = ("flow-smoke-", "flow-green-")
_COLS = ("backlog", "abnormal", "planned", "in_progress", "testing", "verified")


def hide_ws(ws: Path, *, dry_run: bool) -> int:
    if not (ws / ".ccc" / "board").is_dir():
        return 0
    store = FileBoardStore(ws)
    n = 0
    for col in _COLS:
        for t in list(store.list_tasks(col)):
            tid = t.get("id") or ""
            if not any(tid.startswith(p) for p in _PREFIXES):
                continue
            if t.get("card_kind") == "epic" and t.get("split_status") == "done":
                continue
            if t.get("ui_hidden"):
                continue
            print(f"{'DRY ' if dry_run else ''}hide {ws.name} {col} {tid} ss={t.get('split_status')}")
            if not dry_run:
                store.patch_task(tid, {"ui_hidden": True})
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Hide failed smoke/green epics")
    ap.add_argument("--workspace", help="single workspace")
    ap.add_argument("--all-engine", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.workspace:
        wss = [Path(args.workspace).expanduser().resolve()]
    elif args.all_engine:
        from _workspace_registry import list_engine_paths

        wss = [Path(p) for p in list_engine_paths()]
    else:
        print("need --workspace or --all-engine", file=sys.stderr)
        return 2

    total = 0
    for ws in wss:
        total += hide_ws(ws, dry_run=args.dry_run)
    print(f"total={total} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

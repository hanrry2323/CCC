#!/usr/bin/env python3
"""ccc-failure-report.py — 打印最近失败账本（v0.40）

用法:
  python3 scripts/ccc-failure-report.py --last 20
  python3 scripts/ccc-failure-report.py --workspace ~/program/CCC --last 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from _failure_ledger import read_failures  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="CCC failure ledger report")
    ap.add_argument(
        "--workspace",
        default=str(SCRIPTS.parent),
        help="workspace root (default: CCC repo)",
    )
    ap.add_argument("--last", type=int, default=20)
    ap.add_argument("--json", action="store_true", help="raw JSON lines")
    args = ap.parse_args()
    ws = Path(args.workspace).expanduser().resolve()
    rows = read_failures(ws, last=args.last)
    if not rows:
        print(f"(no failures in {ws}/.ccc/stats/failures.jsonl)")
        return 0
    if args.json:
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        return 0
    print(f"=== last {len(rows)} failures @ {ws.name} ===\n")
    for r in reversed(rows):
        print(
            f"[{r.get('ts')}] {r.get('task_id')}  role={r.get('role')}  "
            f"phase={r.get('phase')}  exit={r.get('exit_code')}"
        )
        print(f"  reason: {r.get('reason')}")
        if r.get("stderr_path"):
            print(f"  stderr: {r.get('stderr_path')}")
        tail = (r.get("stderr_tail") or "").strip()
        if tail:
            print("  --- stderr_tail ---")
            for line in tail.splitlines()[-8:]:
                print(f"  | {line}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

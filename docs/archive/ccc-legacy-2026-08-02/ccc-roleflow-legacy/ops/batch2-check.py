#!/usr/bin/env python3
"""Batch2 board snapshot for autonomy ticks. Exit: 0=done, 1=in_progress, 2=hard_fail, 3=stuck."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

WS = Path("/Users/apple/program/clawmed-ccc")
TARGETS = [
    "cla-b1--qx--1-vded",
    "cla-b1-1-migrate",
    "cla-obs1-commit",
    "cla-obs2-pytest",
    "cla-obs5-marker",
]
DONE = {"verified", "released"}
ACTIVE = {"planned", "in_progress", "testing"}


def find_col(tid: str) -> str | None:
    board = WS / ".ccc" / "board"
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        if (board / col / f"{tid}.jsonl").exists():
            return col
    return None


def engine_alive() -> bool:
    hb = WS / ".ccc" / "engine-heartbeat.json"
    if not hb.exists():
        return False
    try:
        age = time.time() - hb.stat().st_mtime
        return age < 120
    except OSError:
        return False


def main() -> int:
    cols = {tid: find_col(tid) for tid in TARGETS}
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cols": cols, "engine_alive": engine_alive()}, ensure_ascii=False, indent=2))
    missing = [t for t, c in cols.items() if c is None]
    done = [t for t, c in cols.items() if c in DONE]
    active = [t for t, c in cols.items() if c in ACTIVE]
    backlog = [t for t, c in cols.items() if c == "backlog"]
    abnormal = [t for t, c in cols.items() if c == "abnormal"]

    if len(done) == len(TARGETS):
        print("VERDICT: DONE")
        return 0
    if len(abnormal) >= 3 and not active:
        print("VERDICT: HARD_FAIL")
        return 2
    if len(abnormal) == len(TARGETS):
        print("VERDICT: HARD_FAIL")
        return 2
    if not active and backlog and not engine_alive():
        print("VERDICT: STUCK")
        return 3
    if active or backlog:
        print("VERDICT: IN_PROGRESS")
        return 1
    print("VERDICT: UNKNOWN", missing)
    return 3


if __name__ == "__main__":
    sys.exit(main())

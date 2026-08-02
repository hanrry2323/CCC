#!/usr/bin/env python3
"""Paper / DRY_RUN intent probe template for business apps (LPSN · P).

Prefer Engine `script_seed` short path (executor_intent=python) over OpenCode.
Copy/customize into apps as scripts/paper_intent_probe.py:

  DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper

Exit 0 = harness green. Never place real orders.
"""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="paper")
    args = ap.parse_args()
    if os.environ.get("DRY_RUN", "").lower() not in ("1", "true", "yes"):
        print("FAIL: set DRY_RUN=true for intent probe", file=sys.stderr)
        return 2
    if str(args.env).lower() not in ("paper", "testnet", "dry"):
        print(f"FAIL: bad env {args.env!r}", file=sys.stderr)
        return 2
    print(f"paper_intent_probe: ok env={args.env}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

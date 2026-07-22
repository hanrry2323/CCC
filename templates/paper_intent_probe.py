#!/usr/bin/env python3
"""Paper / DRY_RUN intent probe template for business apps (LPSN · P).

Copy into a registered app as scripts/paper_intent_probe.py and wire into ## 验收:
  - DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py
  or: DRY_RUN=true python3 scripts/paper_intent_probe.py

Exit 0 = intent probe green; non-zero = fail acceptance / regress.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    if os.environ.get("DRY_RUN", "").lower() not in ("1", "true", "yes"):
        print("FAIL: set DRY_RUN=true for intent probe", file=sys.stderr)
        return 2
    # App-specific checks go here (import paper path, ping mock exchange, …)
    print("paper_intent_probe: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

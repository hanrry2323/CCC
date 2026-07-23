#!/usr/bin/env python3
"""ccc-capacity-probe.py — Mac2017 跨仓并发阶梯探针（只读量测 + 建议档）。

不改同仓 OpenCode=1。读 host-resources + 当前 CCC_MAX_CONCURRENT。

用法:
  python3 scripts/ccc-capacity-probe.py summary
  python3 scripts/ccc-capacity-probe.py recommend --target-apps 10
  python3 scripts/ccc-capacity-probe.py write-brief
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

OUT = Path.home() / ".ccc" / "stats" / "capacity-probe.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def current_max_concurrent() -> int:
    return max(1, int(os.environ.get("CCC_MAX_CONCURRENT", "4") or "4"))


def host_summary(n: int = 200) -> dict:
    from _host_resources import summarize

    return summarize(n=n)


def recommend(target_apps: int = 10) -> dict:
    hs = host_summary(200)
    cur = current_max_concurrent()
    verdict = hs.get("verdict") or "collecting"
    # hard ceiling: min(target_apps, global opencode slots default 6, cpu-ish)
    ncpu = int(hs.get("ncpu") or 8)
    soft_cap = min(target_apps, max(4, ncpu), 10)
    global_oc = 6
    suggested = cur
    reason = ""
    if verdict == "headroom" and cur < soft_cap:
        suggested = min(cur + 1, soft_cap, global_oc + 2)
        reason = (
            f"headroom → try CCC_MAX_CONCURRENT={suggested} "
            f"(cap soft={soft_cap}, watch same-ws mutex + hang)"
        )
    elif verdict == "saturated":
        suggested = max(2, cur - 1)
        reason = "saturated → step down; fix hang/reap before raising"
    elif verdict in ("borderline", "collecting"):
        suggested = cur
        reason = f"{verdict} → hold at {cur}; need ≥30 busy samples"
    else:
        suggested = cur
        reason = f"verdict={verdict}; hold"
    return {
        "generated_at": _now(),
        "current_max_concurrent": cur,
        "suggested_max_concurrent": suggested,
        "target_apps": target_apps,
        "soft_cap": soft_cap,
        "global_opencode_max_note": global_oc,
        "same_ws_opencode": 1,
        "host": hs,
        "reason": reason,
    }


def cmd_summary(_: argparse.Namespace) -> int:
    print(json.dumps(host_summary(200), ensure_ascii=False, indent=2))
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    print(json.dumps(recommend(args.target_apps), ensure_ascii=False, indent=2))
    return 0


def cmd_write_brief(args: argparse.Namespace) -> int:
    rec = recommend(args.target_apps)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(json.dumps({k: rec[k] for k in (
        "current_max_concurrent",
        "suggested_max_concurrent",
        "reason",
    )}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("summary")
    pr = sub.add_parser("recommend")
    pr.add_argument("--target-apps", type=int, default=10)
    pw = sub.add_parser("write-brief")
    pw.add_argument("--target-apps", type=int, default=10)
    args = p.parse_args()
    if args.cmd == "summary":
        return cmd_summary(args)
    if args.cmd == "recommend":
        return cmd_recommend(args)
    if args.cmd == "write-brief":
        return cmd_write_brief(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

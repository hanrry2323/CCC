#!/usr/bin/env python3
"""ccc-host-resources.py — Mac2017 CPU/内存曲线 CLI

Usage:
  python3 scripts/ccc-host-resources.py sample          # 立刻采样写入
  python3 scripts/ccc-host-resources.py summary         # p50/p95 + 并行容量建议
  python3 scripts/ccc-host-resources.py tail [--n 40]   # 最近点 + sparkline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _host_resources import (  # noqa: E402
    collect_sample,
    append_sample,
    read_recent,
    summarize,
    sparkline,
    HOST_RESOURCES_PATH,
)


def cmd_sample(_args: argparse.Namespace) -> int:
    s = collect_sample()
    append_sample(s)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print(f"# wrote {HOST_RESOURCES_PATH}", file=sys.stderr)
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    s = summarize(n=args.n)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    rows = read_recent(args.n)
    loads = []
    mems = []
    for r in rows:
        lr = r.get("load_ratio")
        if lr is None:
            load1 = (r.get("load") or {}).get("1")
            cpus = r.get("ncpu") or 1
            lr = (float(load1) / float(cpus)) if load1 is not None else None
        loads.append(lr)
        mems.append((r.get("memory") or {}).get("used_pct"))
    print(f"path: {HOST_RESOURCES_PATH}")
    print(f"n={len(rows)}")
    print(f"load_ratio: {sparkline(loads)}")
    print(f"mem_pct:    {sparkline(mems)}")
    if rows:
        last = rows[-1]
        print(
            f"last: load1={(last.get('load') or {}).get('1')} "
            f"ratio={last.get('load_ratio')} "
            f"mem={(last.get('memory') or {}).get('used_pct')}% "
            f"opencode_n={last.get('opencode_n')} "
            f"active_dev={last.get('active_dev')}/{last.get('max_concurrent')}"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Mac2017 host resource curve")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample", help="force one sample")
    p_sum = sub.add_parser("summary", help="p50/p95 + headroom verdict")
    p_sum.add_argument("--n", type=int, default=180)
    p_tail = sub.add_parser("tail", help="sparkline of recent samples")
    p_tail.add_argument("--n", type=int, default=60)
    args = ap.parse_args()
    if args.cmd == "sample":
        return cmd_sample(args)
    if args.cmd == "summary":
        return cmd_summary(args)
    if args.cmd == "tail":
        return cmd_tail(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

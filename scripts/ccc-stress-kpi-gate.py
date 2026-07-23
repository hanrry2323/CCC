#!/usr/bin/env python3
"""Stress KPI scorecard gate — compare efficiency.json to references/stress-kpi-scorecard.json.

  python3 scripts/ccc-stress-kpi-gate.py --run stress-mx-20260723r2
  python3 scripts/ccc-stress-kpi-gate.py --efficiency ~/.ccc/stress-matrix/foo-efficiency.json

Exit codes:
  0 PASS (all gates ok, not INVALID)
  1 FAIL (one or more gates failed)
  2 INVALID (observation gate failed — run not usable as pass)
  3 usage / missing inputs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCORECARD = REPO / "references" / "stress-kpi-scorecard.json"
DEFAULT_OUT = Path.home() / ".ccc" / "stress-matrix"


def _get_path(obj: dict[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def enrich_computed(report: dict[str, Any]) -> dict[str, Any]:
    """Derive fields the scorecard expects."""
    epics = report.get("epics") or []
    ss_counts: dict[str, int] = {}
    for e in epics:
        ss = str(e.get("split_status") or "unknown")
        ss_counts[ss] = ss_counts.get(ss, 0) + 1
    # Merge counter from report (may omit done if collector only lists active)
    for k, v in (report.get("epic_split_status") or {}).items():
        ss_counts[str(k)] = max(int(ss_counts.get(str(k), 0)), int(v))

    done = int(ss_counts.get("done", 0))
    failed = int(ss_counts.get("failed", 0))
    running = int(ss_counts.get("running", 0))
    planned = int(ss_counts.get("planned", 0))
    pending = int(ss_counts.get("pending", 0))

    dispatch = report.get("dispatch") or {}
    dispatch_n = int(dispatch.get("ok") or 0) or len(dispatch.get("rows") or [])
    # efficiency report often lists only non-done epics — infer done from dispatch
    accounted = failed + running + planned + pending
    if dispatch_n and done + accounted < dispatch_n:
        done = max(done, dispatch_n - accounted)
        ss_counts["done"] = done

    denom = done + failed + running + planned + pending
    for k, v in ss_counts.items():
        if k not in ("done", "failed", "running", "planned", "pending"):
            denom += int(v)
    # Prefer dispatch_n as denom when it matches a full matrix
    if dispatch_n and dispatch_n >= denom:
        denom = dispatch_n
    epic_done_rate = round(done / denom, 4) if denom else 0.0

    works = report.get("works") or []
    ghost = 0
    for w in works:
        if w.get("col") != "in_progress":
            continue
        title = str(w.get("title") or "")
        if w.get("t_testing") is None and (
            ".ccc/board" in title
            or "卫生" in title
            or "board" in title.lower()
            or (w.get("dev_wall_s") is None and w.get("gate_wall_s") is None)
        ):
            ghost += 1

    pre = (report.get("computed") or {}).get("ghost_in_progress_n")
    if isinstance(pre, int):
        ghost = pre

    computed = {
        "epic_done_rate": epic_done_rate,
        "epic_ss_counts": ss_counts,
        "epic_denom": denom,
        "epic_done_n": done,
        "dispatch_n": dispatch_n,
        "ghost_in_progress_n": ghost,
        "work_abnormal_n": int((report.get("work_columns") or {}).get("abnormal") or 0),
        "work_in_progress_n": int((report.get("work_columns") or {}).get("in_progress") or 0),
    }
    out = dict(report)
    out["computed"] = {**(report.get("computed") or {}), **computed}
    return out


def _cmp(op: str, actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    try:
        a = float(actual)
        e = float(expected)
    except (TypeError, ValueError):
        return False
    if op == ">=":
        return a >= e
    if op == "<=":
        return a <= e
    if op == "==":
        return a == e
    if op == ">":
        return a > e
    if op == "<":
        return a < e
    raise ValueError(f"unknown op {op}")


def evaluate(report: dict[str, Any], scorecard: dict[str, Any]) -> dict[str, Any]:
    enriched = enrich_computed(report)
    rows: list[dict[str, Any]] = []
    for g in scorecard.get("gates") or []:
        gid = g["id"]
        path = g["path"]
        actual = _get_path(enriched, path)
        if path.startswith("computed."):
            actual = (enriched.get("computed") or {}).get(path.split(".", 1)[1])
        ok = _cmp(g["op"], actual, g["value"])
        rows.append(
            {
                "id": gid,
                "path": path,
                "op": g["op"],
                "expected": g["value"],
                "actual": actual,
                "ok": ok,
                "primary": bool(g.get("primary")),
                "hard_red": bool(g.get("hard_red")),
                "invalidates_run_if_fail": bool(g.get("invalidates_run_if_fail")),
                "note": g.get("note") or "",
            }
        )

    primary_fail = [r["id"] for r in rows if r["primary"] and not r["ok"]]
    all_ok = all(r["ok"] for r in rows)
    failed = [r for r in rows if not r["ok"]]
    if not failed:
        verdict = "PASS"
    elif any(r["hard_red"] for r in failed) or any(r["primary"] for r in failed):
        verdict = "FAIL"
    elif all(r["invalidates_run_if_fail"] for r in failed):
        verdict = "INVALID"
    else:
        verdict = "FAIL"

    return {
        "schema_version": "1.0",
        "run": enriched.get("run"),
        "generated_at": enriched.get("generated_at"),
        "scorecard_id": scorecard.get("id"),
        "verdict": verdict,
        "all_ok": all_ok,
        "primary_fail": primary_fail,
        "gates": rows,
        "computed": enriched.get("computed"),
        "bottlenecks_hint": enriched.get("bottlenecks_hint") or [],
    }


def load_scorecard(path: Path | None = None) -> dict[str, Any]:
    p = path or SCORECARD
    return json.loads(p.read_text(encoding="utf-8"))


def load_efficiency(run: str | None, efficiency: Path | None, out_dir: Path) -> dict[str, Any]:
    if efficiency:
        return json.loads(efficiency.read_text(encoding="utf-8"))
    if not run:
        raise SystemExit("need --run or --efficiency")
    p = out_dir / f"{run}-efficiency.json"
    if not p.is_file():
        raise SystemExit(f"missing {p}; run ccc-stress-efficiency-report.py first")
    return json.loads(p.read_text(encoding="utf-8"))


def render_md(result: dict[str, Any]) -> str:
    lines = [
        f"# KPI gate `{result.get('run')}`",
        "",
        f"- scorecard: `{result.get('scorecard_id')}`",
        f"- verdict: **{result.get('verdict')}**",
        f"- primary_fail: `{result.get('primary_fail')}`",
        "",
        "| id | op | expected | actual | ok | primary |",
        "|----|----|----------|--------|----|---------|",
    ]
    for r in result.get("gates") or []:
        lines.append(
            f"| `{r['id']}` | {r['op']} | {r['expected']} | {r['actual']} | "
            f"{'✅' if r['ok'] else '❌'} | {r['primary']} |"
        )
    lines += ["", "### computed", "", f"```json\n{json.dumps(result.get('computed'), ensure_ascii=False, indent=2)}\n```", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CCC stress KPI scorecard gate")
    ap.add_argument("--run", default="")
    ap.add_argument("--efficiency", type=Path, default=None)
    ap.add_argument("--scorecard", type=Path, default=SCORECARD)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--write", action="store_true", help="write *-kpi-gate.{json,md}")
    args = ap.parse_args(argv)

    try:
        scorecard = load_scorecard(args.scorecard)
        report = load_efficiency(args.run or None, args.efficiency, args.out)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 3

    result = evaluate(report, scorecard)
    print(json.dumps({k: result[k] for k in ("run", "verdict", "primary_fail", "computed")}, ensure_ascii=False, indent=2))
    for r in result["gates"]:
        mark = "OK" if r["ok"] else "FAIL"
        print(f"  [{mark}] {r['id']}: actual={r['actual']} {r['op']} {r['expected']}")

    if args.write or args.run:
        args.out.mkdir(parents=True, exist_ok=True)
        run = result.get("run") or args.run or "unknown"
        jp = args.out / f"{run}-kpi-gate.json"
        mp = args.out / f"{run}-kpi-gate.md"
        jp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        mp.write_text(render_md(result), encoding="utf-8")
        print(f"wrote {jp}")
        print(f"wrote {mp}")

    v = result["verdict"]
    if v == "PASS":
        return 0
    if v == "INVALID":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

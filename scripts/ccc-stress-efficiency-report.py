#!/usr/bin/env python3
"""Generate stress-matrix efficiency report (next-dev baseline data).

Run on Mac2017 after / during stress-mx batch:

  python3 scripts/ccc-stress-efficiency-report.py --run stress-mx-20260722

Writes:
  ~/.ccc/stress-matrix/<run>-efficiency.json
  ~/.ccc/stress-matrix/<run>-efficiency.md

Sources: stress JSON, board columns, board events, opencode-timings,
host-resources, git log, workspace failures.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

APPS_DEFAULT = ("ccc-demo", "qb")
APPS_ROOT = Path.home() / "program" / "apps"

# Same-epic multi-phase tail: …-w2, …-w3 — queue wait includes waiting on prior phase
_SERIAL_SUCCESSOR_RE = re.compile(r"-w(\d+)$", re.IGNORECASE)


def _is_serial_successor_work(work_id: str) -> bool:
    """True for -w2+ cards (dependency-chain successors under same epic)."""
    m = _SERIAL_SUCCESSOR_RE.search((work_id or "").strip())
    if not m:
        return False
    try:
        return int(m.group(1)) >= 2
    except ValueError:
        return False


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _sec(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return max(0.0, (b - a).total_seconds())


def _pct(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return round(s[0], 2)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 2)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict):
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out


def _board_events(ws: Path, tid: str) -> list[dict]:
    return _load_jsonl(ws / ".ccc" / "board" / "events" / f"{tid}.events.jsonl")


def _moves(events: list[dict]) -> list[tuple[datetime, str, str]]:
    moves: list[tuple[datetime, str, str]] = []
    for r in events:
        if r.get("event") not in (None, "move") and r.get("event") != "move":
            # accept rows that look like moves
            if "to" not in r and "to_col" not in r:
                continue
        to = r.get("to") or r.get("to_col")
        fr = r.get("from") or r.get("from_col") or "none"
        ts = _parse_ts(r.get("timestamp") or r.get("t") or r.get("ts"))
        if to and ts:
            moves.append((ts, str(fr), str(to)))
    moves.sort(key=lambda x: x[0])
    return moves


def _first_to(moves: list[tuple[datetime, str, str]], col: str) -> datetime | None:
    for ts, _fr, to in moves:
        if to == col:
            return ts
    return None


def _last_to(moves: list[tuple[datetime, str, str]], col: str) -> datetime | None:
    hit = None
    for ts, _fr, to in moves:
        if to == col:
            hit = ts
    return hit


def _git_commits(ws: Path, needle: str) -> list[dict]:
    try:
        r = subprocess.run(
            [
                "git",
                "-C",
                str(ws),
                "log",
                "--since=2026-07-20",
                "--pretty=format:%H|%cI|%s",
                f"--grep={needle}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for ln in (r.stdout or "").splitlines():
        if "|" not in ln:
            continue
        h, ci, subj = ln.split("|", 2)
        rows.append({"hash": h[:10], "ts": ci, "subject": subj})
    return rows


def collect(run: str, apps: tuple[str, ...]) -> dict[str, Any]:
    from _board_store import FileBoardStore

    stress_path = Path.home() / ".ccc" / "stress-matrix" / f"{run}.json"
    dispatches: list[dict] = []
    if stress_path.is_file():
        raw = json.loads(stress_path.read_text(encoding="utf-8"))
        dispatches = list(raw.get("dispatches") or [])

    timings = _load_jsonl(Path.home() / ".ccc" / "stats" / "opencode-timings.jsonl")
    host = _load_jsonl(Path.home() / ".ccc" / "stats" / "host-resources.jsonl")

    works: list[dict] = []
    epics: list[dict] = []
    COLS = [
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ]

    for app in apps:
        ws = APPS_ROOT / app
        if not ws.is_dir():
            continue
        store = FileBoardStore(ws)
        for col in COLS:
            for t in store.list_tasks(col):
                tid = str(t.get("id") or "")
                if run not in tid:
                    continue
                row = {
                    "app": app,
                    "id": tid,
                    "col": col,
                    "kind": t.get("card_kind"),
                    "split_status": t.get("split_status"),
                    "complexity": t.get("complexity"),
                    "parent_id": t.get("parent_id"),
                    "title": t.get("title"),
                }
                if t.get("card_kind") == "epic":
                    epics.append(row)
                else:
                    works.append(row)

        for w in works:
            if w["app"] != app:
                continue
            tid = w["id"]
            moves = _moves(_board_events(ws, tid))
            t_planned = _first_to(moves, "planned")
            t_ip = _first_to(moves, "in_progress")
            t_test = _first_to(moves, "testing")
            t_ver = _first_to(moves, "verified")
            t_rel = _first_to(moves, "released")
            t_abn = _first_to(moves, "abnormal")
            # terminal time
            terminal_ts = None
            terminal_col = w["col"]
            for col in ("released", "abnormal", "verified", "testing", "planned"):
                ts = _last_to(moves, col) if col != w["col"] else _last_to(moves, col)
                if w["col"] == col:
                    terminal_ts = _last_to(moves, col) or t_planned
                    terminal_col = col
                    break
            if terminal_ts is None:
                terminal_ts = (
                    t_rel or t_abn or t_ver or t_test or t_ip or t_planned
                )
                terminal_col = w["col"]

            queue_wait = _sec(t_planned, t_ip)
            # if planned→testing skip in_progress, treat as 0 queue after planned
            if queue_wait is None and t_planned and t_test:
                queue_wait = _sec(t_planned, t_test)
            dev_wall = _sec(t_ip, t_test)
            gate_wall = None
            if t_test:
                gate_end = t_ver or t_rel or t_abn or _last_to(moves, "planned")
                gate_wall = _sec(t_test, gate_end)
            e2e = _sec(t_planned, terminal_ts)

            fail_loops = sum(
                1
                for _ts, fr, to in moves
                if fr == "testing" and to in ("planned", "abnormal")
            )
            w.update(
                {
                    "t_planned": t_planned.isoformat() if t_planned else None,
                    "t_in_progress": t_ip.isoformat() if t_ip else None,
                    "t_testing": t_test.isoformat() if t_test else None,
                    "t_verified": t_ver.isoformat() if t_ver else None,
                    "t_released": t_rel.isoformat() if t_rel else None,
                    "t_abnormal": t_abn.isoformat() if t_abn else None,
                    "queue_wait_s": round(queue_wait, 1) if queue_wait is not None else None,
                    "dev_wall_s": round(dev_wall, 1) if dev_wall is not None else None,
                    "gate_wall_s": round(gate_wall, 1) if gate_wall is not None else None,
                    "e2e_work_s": round(e2e, 1) if e2e is not None else None,
                    "fail_loops": fail_loops,
                    "move_n": len(moves),
                    "git_commits": len(_git_commits(ws, tid)),
                }
            )

    # timings aggregate
    dones = [
        r
        for r in timings
        if r.get("event") == "opencode_done" and run in str(r.get("task") or "")
    ]
    starts = [
        r
        for r in timings
        if r.get("event") == "opencode_start" and run in str(r.get("task") or "")
    ]

    def agg_times(rows: list[dict], key: str) -> dict:
        vals = [float(r[key]) for r in rows if r.get(key) is not None]
        return {
            "n": len(vals),
            "p50": _pct(vals, 50),
            "p95": _pct(vals, 95),
            "max": round(max(vals), 2) if vals else None,
            "mean": round(statistics.mean(vals), 2) if vals else None,
        }

    by_cx: dict[str, list] = defaultdict(list)
    for r in dones:
        by_cx[str(r.get("complexity") or "?")].append(r)

    # Always emit full column set (missing key ≠ 0 breaks count gates).
    _WORK_COLS = (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    )
    work_by_col = {c: 0 for c in _WORK_COLS}
    work_by_col.update(Counter(w["col"] for w in works))
    epic_by_ss = Counter((e.get("split_status") or "?") for e in epics)

    queue_vals = [w["queue_wait_s"] for w in works if w.get("queue_wait_s") is not None]
    # R5: independent cards = exclude same-epic serial successors (-w2+)
    for w in works:
        w["serial_successor"] = _is_serial_successor_work(str(w.get("id") or ""))
        w["queue_cohort"] = (
            "serial_successor" if w["serial_successor"] else "independent"
        )
    queue_indep_vals = [
        w["queue_wait_s"]
        for w in works
        if w.get("queue_wait_s") is not None and not w.get("serial_successor")
    ]
    queue_succ_vals = [
        w["queue_wait_s"]
        for w in works
        if w.get("queue_wait_s") is not None and w.get("serial_successor")
    ]
    dev_vals = [w["dev_wall_s"] for w in works if w.get("dev_wall_s") is not None]
    gate_vals = [w["gate_wall_s"] for w in works if w.get("gate_wall_s") is not None]
    e2e_vals = [w["e2e_work_s"] for w in works if w.get("e2e_work_s") is not None]

    host_summary = None
    try:
        from _host_resources import summarize

        host_summary = summarize(host if host else None, n=500)
    except Exception as exc:
        host_summary = {"error": str(exc), "samples": len(host)}

    dispatch_ok = sum(1 for d in dispatches if d.get("ok"))
    report = {
        "run": run,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dispatch": {
            "n": len(dispatches),
            "ok": dispatch_ok,
            "rows": [
                {
                    "app": d.get("app"),
                    "sid": d.get("sid"),
                    "name": d.get("name"),
                    "http": d.get("http"),
                    "ok": d.get("ok"),
                    "epic_id": d.get("epic_id"),
                }
                for d in dispatches
            ],
        },
        "epics": epics,
        "epic_split_status": dict(epic_by_ss),
        "works": works,
        "work_columns": dict(work_by_col),
        "time_agg": {
            "queue_wait_s": {
                "p50": _pct(queue_vals, 50),
                "p95": _pct(queue_vals, 95),
                "max": max(queue_vals) if queue_vals else None,
                "n": len(queue_vals),
            },
            "queue_wait_indep_s": {
                "p50": _pct(queue_indep_vals, 50),
                "p95": _pct(queue_indep_vals, 95),
                "max": max(queue_indep_vals) if queue_indep_vals else None,
                "n": len(queue_indep_vals),
                "note": "excludes serial_successor (-w2+)",
            },
            "queue_wait_successor_s": {
                "p50": _pct(queue_succ_vals, 50),
                "p95": _pct(queue_succ_vals, 95),
                "max": max(queue_succ_vals) if queue_succ_vals else None,
                "n": len(queue_succ_vals),
            },
            "dev_wall_s": {
                "p50": _pct(dev_vals, 50),
                "p95": _pct(dev_vals, 95),
                "max": max(dev_vals) if dev_vals else None,
                "n": len(dev_vals),
            },
            "gate_wall_s": {
                "p50": _pct(gate_vals, 50),
                "p95": _pct(gate_vals, 95),
                "max": max(gate_vals) if gate_vals else None,
                "n": len(gate_vals),
            },
            "e2e_work_s": {
                "p50": _pct(e2e_vals, 50),
                "p95": _pct(e2e_vals, 95),
                "max": max(e2e_vals) if e2e_vals else None,
                "n": len(e2e_vals),
            },
        },
        "opencode_timings": {
            "starts": len(starts),
            "dones": len(dones),
            "wall_s": agg_times(dones, "wall_s"),
            "duration_s": agg_times(dones, "duration_s"),
            "duration_s_fill_rate": (
                round(
                    sum(1 for r in dones if r.get("duration_s") is not None)
                    / max(1, len(dones)),
                    3,
                )
                if dones
                else None
            ),
            "by_complexity": {
                cx: {
                    "n": len(rs),
                    "status": dict(Counter(r.get("status") for r in rs)),
                    "wall_s": agg_times(rs, "wall_s"),
                    "duration_s": agg_times(rs, "duration_s"),
                }
                for cx, rs in sorted(by_cx.items())
            },
        },
        "dev_path": _collect_dev_paths(run, APPS_ROOT),
        "host": host_summary,
        "bottlenecks_hint": _bottlenecks(
            queue_vals, dev_vals, gate_vals, work_by_col, epic_by_ss
        ),
        "concurrency_note": (
            "MAX_CONCURRENT 默认保持 4；仅当 host-resources 忙时样本≥30 且 "
            "headroom + 卡死率低时试 5。同仓仍 1 路 OpenCode。"
        ),
    }
    return report


def _collect_dev_paths(run: str, apps_root: Path) -> dict[str, Any]:
    """Aggregate path=board_ops|script_seed|opencode from events.jsonl."""
    counts: Counter = Counter()
    ok_by: Counter = Counter()
    fail_by: Counter = Counter()
    dirty = 0
    for app in APPS_DEFAULT:
        ev = apps_root / app / ".ccc" / "stats" / "events.jsonl"
        for row in _load_jsonl(ev):
            if run not in str(row.get("task") or ""):
                continue
            if row.get("event") == "dirty_result":
                dirty += 1
            if row.get("event") != "dev_path":
                continue
            path = str(row.get("path") or "unknown")
            counts[path] += 1
            if row.get("ok") is False:
                fail_by[path] += 1
            else:
                ok_by[path] += 1
    total = sum(counts.values()) or 1
    return {
        "counts": dict(counts),
        "ok": dict(ok_by),
        "fail": dict(fail_by),
        "share": {k: round(v / total, 3) for k, v in counts.items()},
        "dirty_result_n": dirty,
    }


def _bottlenecks(
    queue: list[float],
    dev: list[float],
    gate: list[float],
    cols: Counter,
    epic_ss: Counter,
) -> list[str]:
    hints: list[str] = []
    q95 = _pct(queue, 95) or 0
    d95 = _pct(dev, 95) or 0
    g95 = _pct(gate, 95) or 0
    if q95 > max(d95, 1) * 2 and q95 > 300:
        hints.append(
            f"排队主导：queue_wait p95={q95:.0f}s ≫ dev p95={d95:.0f}s（同仓互斥/幽灵槽）"
        )
    if g95 > d95 * 1.5 and g95 > 120:
        hints.append(f"审测偏慢：gate p95={g95:.0f}s > dev p95={d95:.0f}s")
    if cols.get("abnormal", 0):
        hints.append(f"abnormal={cols.get('abnormal')} 张 work 未闭环")
    if epic_ss.get("failed"):
        hints.append(f"epic failed={epic_ss.get('failed')}")
    if cols.get("testing", 0):
        hints.append(f"仍有 testing={cols.get('testing')}（报告未完全收口）")
    if not hints:
        hints.append("未发现明显单一瓶颈（或样本不足）")
    return hints


def render_md(report: dict) -> str:
    ta = report["time_agg"]
    ot = report["opencode_timings"]
    lines = [
        f"# Efficiency report `{report['run']}`",
        "",
        f"generated: `{report['generated_at']}`",
        "",
        "## 1. Executive summary",
        "",
        f"- Dispatches: **{report['dispatch']['ok']}/{report['dispatch']['n']}** ok",
        f"- Works by column: `{report['work_columns']}`",
        f"- Epics split_status: `{report['epic_split_status']}`",
        f"- queue_wait_s p50/p95 (all): **{ta['queue_wait_s']['p50']}** / **{ta['queue_wait_s']['p95']}** (n={ta['queue_wait_s']['n']})",
        f"- queue_wait_indep_s p50/p95: **{(ta.get('queue_wait_indep_s') or {}).get('p50')}** / **{(ta.get('queue_wait_indep_s') or {}).get('p95')}** (n={(ta.get('queue_wait_indep_s') or {}).get('n')}; excl -w2+)",
        f"- dev_wall_s p50/p95: **{ta['dev_wall_s']['p50']}** / **{ta['dev_wall_s']['p95']}** (n={ta['dev_wall_s']['n']})",
        f"- gate_wall_s p50/p95: **{ta['gate_wall_s']['p50']}** / **{ta['gate_wall_s']['p95']}** (n={ta['gate_wall_s']['n']})",
        f"- e2e_work_s p50/p95/max: **{ta['e2e_work_s']['p50']}** / **{ta['e2e_work_s']['p95']}** / **{ta['e2e_work_s']['max']}**",
        "",
        "### Bottlenecks",
        "",
    ]
    for h in report["bottlenecks_hint"]:
        lines.append(f"- {h}")
    lines += [
        "",
        "## 2. Scenario dispatches",
        "",
        "| app | sid | name | http | ok | epic |",
        "|-----|-----|------|------|----|------|",
    ]
    for d in report["dispatch"]["rows"]:
        lines.append(
            f"| {d.get('app')} | {d.get('sid')} | {d.get('name')} | {d.get('http')} | {d.get('ok')} | `{d.get('epic_id') or ''}` |"
        )

    lines += [
        "",
        "## 3. Work timing table",
        "",
        "| app | work | col | cohort | queue_s | dev_s | gate_s | e2e_s | fail_loops |",
        "|-----|------|-----|--------|--------|-------|--------|-------|------------|",
    ]
    for w in sorted(report["works"], key=lambda x: (x["app"], x["id"])):
        lines.append(
            f"| {w['app']} | `{w['id'][-36:]}` | {w['col']} | {w.get('queue_cohort') or '-'} | {w.get('queue_wait_s')} | {w.get('dev_wall_s')} | {w.get('gate_wall_s')} | {w.get('e2e_work_s')} | {w.get('fail_loops')} |"
        )

    lines += [
        "",
        "## 4. OpenCode timings",
        "",
        f"- starts={ot['starts']} dones={ot['dones']}",
        f"- duration_s fill_rate: **{ot.get('duration_s_fill_rate')}**",
        f"- wall_s: `{ot['wall_s']}`",
        f"- duration_s: `{ot['duration_s']}`",
        "",
    ]
    for cx, block in (ot.get("by_complexity") or {}).items():
        lines.append(f"- **{cx}**: `{block}`")

    dp = report.get("dev_path") or {}
    lines += [
        "",
        "## 4b. Dev path share (board_ops / script_seed / opencode)",
        "",
        f"- counts: `{dp.get('counts')}`",
        f"- share: `{dp.get('share')}`",
        f"- fail: `{dp.get('fail')}`",
        f"- dirty_result_n: **{dp.get('dirty_result_n')}**",
        f"- concurrency: {report.get('concurrency_note')}",
        "",
    ]

    lines += [
        "",
        "## 5. Host resources",
        "",
        f"```json\n{json.dumps(report.get('host'), ensure_ascii=False, indent=2)[:2500]}\n```",
        "",
        "## 6. Epics",
        "",
        "| app | epic | split_status | col |",
        "|-----|------|--------------|-----|",
    ]
    for e in sorted(report["epics"], key=lambda x: (x["app"], x["id"])):
        lines.append(
            f"| {e['app']} | `{e['id']}` | {e.get('split_status')} | {e['col']} |"
        )

    lines += [
        "",
        "## 7. Next-dev mapping",
        "",
        "Map findings → `docs/briefs/2026-07-22-opencode-lifecycle-stall.md` A–F and efficiency brief.",
        "",
        "- If queue_wait ≫ dev_wall → lifecycle/slot (A) + same-ws serialization",
        "- If duration_s missing → dirty result.json (B)",
        "- If hygiene in opencode timings → short-path (C)",
        "- If gate_wall high / engine idle CPU 0 → testing blocks tick (D)",
        "- Host headroom only after busy-hour samples",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="stress-mx-20260722")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path.home() / ".ccc" / "stress-matrix",
    )
    ap.add_argument("--apps", default="ccc-demo,qb")
    args = ap.parse_args()
    apps = tuple(a.strip() for a in args.apps.split(",") if a.strip())
    report = collect(args.run, apps)
    args.out.mkdir(parents=True, exist_ok=True)
    jp = args.out / f"{args.run}-efficiency.json"
    mp = args.out / f"{args.run}-efficiency.md"
    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(render_md(report), encoding="utf-8")
    print(f"wrote {jp}")
    print(f"wrote {mp}")
    print("bottlenecks:")
    for h in report["bottlenecks_hint"]:
        print(" -", h)
    ta = report["time_agg"]
    print(
        "queue_p95=",
        ta["queue_wait_s"]["p95"],
        "dev_p95=",
        ta["dev_wall_s"]["p95"],
        "e2e_p95=",
        ta["e2e_work_s"]["p95"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

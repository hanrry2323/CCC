#!/usr/bin/env python3
"""Aggregate CCC Desktop stability ledgers into a metadata-only Markdown report."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _read_jsonl(paths: list[Path], *, since: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            raw_ts = str(row.get("ts") or "")
            try:
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except ValueError:
                ts = None
            if ts is not None:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts.astimezone(timezone.utc) < since:
                    continue
            rows.append(row)
    return rows


def _percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


def _table(counter: Counter[str], *, empty: str = "无") -> str:
    if not counter:
        return empty
    return "\n".join(f"| `{key or 'none'}` | {count} |" for key, count in counter.most_common())


def build_report(desktop: list[dict[str, Any]], sidecar: list[dict[str, Any]]) -> str:
    desktop_terminal = [r for r in desktop if r.get("event") in ("ok", "fail")]
    ok = sum(1 for r in desktop_terminal if r.get("event") == "ok")
    failed = len(desktop_terminal) - ok
    success_rate = (100.0 * ok / len(desktop_terminal)) if desktop_terminal else None
    durations = [
        int(r["duration_ms"])
        for r in desktop_terminal
        if isinstance(r.get("duration_ms"), (int, float))
    ]
    first_delta = [
        int(r["first_delta_ms"])
        for r in desktop
        if isinstance(r.get("first_delta_ms"), (int, float))
    ]
    failure_codes = Counter(str(r.get("code") or "unknown") for r in desktop if r.get("event") == "fail")
    heal_codes = Counter(str(r.get("code") or "unknown") for r in desktop if r.get("heal_drop") is True)
    hub_transitions = Counter(
        "reachable" if r.get("reachable") is True else "unreachable"
        for r in desktop
        if r.get("event") == "hub_reachability"
    )
    flow_events = Counter(str(r.get("event") or "") for r in desktop if str(r.get("event") or "").startswith("flow_"))
    sidecar_codes = Counter(str(r.get("code") or "none") for r in sidecar if r.get("event") == "turn_end")
    matched = len(
        {str(r.get("turn_id")) for r in desktop if r.get("turn_id")}
        & {str(r.get("turn_id")) for r in sidecar if r.get("turn_id")}
    )

    rate = "n/a" if success_rate is None else f"{success_rate:.2f}%"
    return f"""# CCC Desktop stability report

## Summary

- Desktop terminal turns: **{len(desktop_terminal)}**
- Successful turns: **{ok}**
- Failed turns: **{failed}**
- Success rate: **{rate}**
- Cross-layer matched `turn_id`: **{matched}**
- Turn duration P50 / P95: **{_percentile(durations, 0.50) or 'n/a'} ms / {_percentile(durations, 0.95) or 'n/a'} ms**
- First-delta P50 / P95: **{_percentile(first_delta, 0.50) or 'n/a'} ms / {_percentile(first_delta, 0.95) or 'n/a'} ms**

## Desktop failure codes

| Code | Count |
|---|---:|
{_table(failure_codes)}

## Heal-drop reasons

| Code | Count |
|---|---:|
{_table(heal_codes)}

## Sidecar terminal codes

| Code | Count |
|---|---:|
{_table(sidecar_codes)}

## Hub reachability transitions

| State | Count |
|---|---:|
{_table(hub_transitions)}

## Flow connection events

| Event | Count |
|---|---:|
{_table(flow_events)}

> This report reads metadata-only ledgers. It does not include prompts, message bodies, credentials, or file contents.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    logs = Path.home() / "Library" / "Logs" / "CCC"
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, args.hours))
    desktop = _read_jsonl(
        [logs / "desktop-chat-turns.jsonl.1", logs / "desktop-chat-turns.jsonl"],
        since=since,
    )
    sidecar = _read_jsonl(
        [logs / "agent-sidecar-turns.jsonl.2", logs / "agent-sidecar-turns.jsonl.1", logs / "agent-sidecar-turns.jsonl"],
        since=since,
    )
    report = build_report(desktop, sidecar)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

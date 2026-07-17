#!/usr/bin/env python3
"""ccc-daily-docs-review.py — 文档债日审（infrastructure / README / CHANGELOG）。

用法:
  python3 scripts/ccc-daily-docs-review.py [--workspace PATH] [--apply]
  --apply: 对可行动发现建 backlog（tags: ops-auto, docs-review）；默认只报告。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CCC daily docs review")
    ap.add_argument("--workspace", default=str(SCRIPTS.parent))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    apply = bool(args.apply) and not args.dry_run

    from _ops_probe import docs_debt_scan, adopt_suggestion

    # scan registered + current
    spaces = {ws.name if ws.name != "CCC" else "CCC": str(ws)}
    try:
        from chat_server.routers.projects import PROJECTS, PROJECT_TO_WORKSPACE, reload_projects

        reload_projects()
        for pid, info in PROJECTS.items():
            wsid = PROJECT_TO_WORKSPACE.get(pid, pid)
            spaces[wsid] = info["path"]
    except Exception:
        spaces["CCC"] = str(SCRIPTS.parent)

    scan = docs_debt_scan(spaces)
    findings = scan.get("findings") or []

    spawned = []
    if apply:
        for f in findings:
            if f.get("severity") not in ("medium", "high"):
                continue
            title = f"文档: {f.get('title') or 'docs debt'}"
            target_ws = f.get("workspace")
            target_path = Path(spaces.get(target_ws, str(ws))).expanduser() if target_ws else ws
            if not target_path.is_dir():
                target_path = ws
            r = adopt_suggestion(
                target_path,
                title=title[:200],
                description=f.get("suggestion") or json.dumps(f, ensure_ascii=False),
                tags=["ops-auto", "docs-review", f.get("kind") or "docs"],
            )
            spawned.append(r)

    day = datetime.now().strftime("%Y-%m-%d")
    report_dir = ws / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"docs-review-{day}.md"
    lines = [
        f"# Docs Review {day}",
        "",
        f"- ts: {_now()}",
        f"- findings: {len(findings)}",
        f"- apply: {apply}",
        "",
    ]
    for f in findings:
        lines.append(
            f"- **{f.get('severity')}** [{f.get('kind')}] {f.get('title')} — {f.get('suggestion')}"
        )
    if spawned:
        lines.append("")
        lines.append("## Spawned")
        for s in spawned:
            lines.append(f"- {json.dumps(s, ensure_ascii=False)}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = {
        "ok": True,
        "findings": findings,
        "spawned": spawned,
        "apply": apply,
        "report": str(report_path),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

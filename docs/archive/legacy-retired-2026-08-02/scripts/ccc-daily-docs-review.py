#!/usr/bin/env python3
"""ccc-daily-docs-review.py — 文档债日审（infrastructure / README / CHANGELOG）。

用法:
  python3 scripts/ccc-daily-docs-review.py [--workspace PATH] [--all-apps] [--apply]
  --apply: 对可行动发现建 backlog（tags: ops-auto, docs-review）；仅 engine-eligible 业务仓。
  默认只报告。禁止往 CCC orch 供弹。
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
    ap.add_argument("--workspace", default="", help="report output root (default CCC home)")
    ap.add_argument("--all-apps", action="store_true", help="scan engine-eligible apps only")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    report_ws = Path(args.workspace or SCRIPTS.parent).expanduser().resolve()
    apply = bool(args.apply) and not args.dry_run

    from _ops_probe import adopt_suggestion, docs_debt_scan, list_ammo_workspaces

    spaces: dict[str, str] = {}
    for item in list_ammo_workspaces():
        spaces[item["workspace"]] = item["path"]
    if not spaces and not args.all_apps:
        # dry report may still scan infra-only findings with empty app map
        spaces = {}

    scan = docs_debt_scan(spaces)
    findings = scan.get("findings") or []

    spawned = []
    if apply:
        for f in findings:
            if f.get("severity") not in ("medium", "high"):
                continue
            title = f"文档: {f.get('title') or 'docs debt'}"
            target_ws = f.get("workspace")
            if not target_ws or target_ws not in spaces:
                spawned.append(
                    {
                        "ok": False,
                        "skipped": True,
                        "reason": "finding lacks engine-eligible workspace",
                        "title": title,
                    }
                )
                continue
            r = adopt_suggestion(
                spaces[target_ws],
                title=title[:200],
                description=f.get("suggestion") or json.dumps(f, ensure_ascii=False),
                tags=["ops-auto", "docs-review", f.get("kind") or "docs"],
            )
            spawned.append(r)

    day = datetime.now().strftime("%Y-%m-%d")
    report_dir = report_ws / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"docs-review-{day}.md"
    lines = [
        f"# Docs Review {day}",
        "",
        f"- ts: {_now()}",
        f"- findings: {len(findings)}",
        f"- apply: {apply}",
        f"- ammo_workspaces: {len(spaces)}",
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
        "ammo_workspaces": list(spaces.keys()),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

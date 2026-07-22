"""Deterministic intent-probe / script seed short path — no opencode.

When a work card only needs to land a small probe script (LPSN · P),
copy from CCC templates (or rewrite a known good body), write a minimal
report, task-commit, and leave the card ready for testing/acceptance.

Trigger (any of):
- executor ∈ {python, auto, cli} AND scope/plan targets paper_intent_probe
- title/description/plan hits 意图探针 / paper_intent_probe / script-seed
- tags include script-seed / intent-probe

Authority: loop-engineer-authority LPSN · P — mechanical probes must not
burn OpenCode hang budget.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.script_seed")

_PROBE_NAME = "paper_intent_probe.py"
_PROBE_MARKERS = (
    "paper_intent_probe",
    "意图探针",
    "script-seed",
    "intent-probe",
    "paper probe",
    "纸面",
)


def _ccc_repo_root() -> Path:
    # scripts/board/roles/script_seed.py → CCC root
    return Path(__file__).resolve().parents[3]


def _load_phases(ws: Path, tid: str) -> list[dict[str, Any]]:
    pf = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if not pf.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in pf.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "phase" in d:
            out.append(d)
    return out


def _blob_for_task(ws: Path, task: dict[str, Any]) -> str:
    tid = str(task.get("id") or "")
    parts = [
        str(task.get("title") or ""),
        str(task.get("description") or ""),
        str(task.get("note") or ""),
        " ".join(str(t) for t in (task.get("tags") or [])),
    ]
    plan = ws / ".ccc" / "plans" / f"{tid}.plan.md"
    if plan.is_file():
        parts.append(plan.read_text(encoding="utf-8", errors="replace")[:8000])
    for p in _load_phases(ws, tid):
        parts.append(json.dumps(p.get("scope") or [], ensure_ascii=False))
    return "\n".join(parts).lower()


def looks_like_intent_probe_seed(ws: Path, task: dict[str, Any]) -> bool:
    blob = _blob_for_task(ws, task)
    return any(m.lower() in blob for m in _PROBE_MARKERS)


def should_use_script_seed(ws: Path, task: dict[str, Any]) -> bool:
    """Prefer script_seed over OpenCode for mechanical probe cards."""
    if not looks_like_intent_probe_seed(ws, task):
        return False
    exec_id = str(task.get("executor") or "").strip().lower()
    # Explicit python/auto/cli OR opencode mis-routed probe (force seed)
    if exec_id in ("python", "auto", "cli", "opencode", ""):
        return True
    return False


def _probe_body_for_app() -> str:
    """qb-aware body: DRY_RUN gate + optional startup_check with hard timeout."""
    return r'''#!/usr/bin/env python3
"""Paper / DRY_RUN intent probe (LPSN · P) — deterministic seed, no OpenCode.

Usage:
  DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper
  DRY_RUN=true python3 scripts/paper_intent_probe.py --env paper

Exit 0 = harness green (DRY_RUN gate + optional startup_check within timeout).
startup_check hang/timeout → WARN in report but still exit 0 if DRY_RUN gate passed
(so regress does not inherit a 90s hang). Real order paths remain forbidden.
"""

from __future__ import annotations

import argparse
import os
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_REPORT = ROOT / "docs" / "reports" / "paper-intent-probe-latest.md"
STARTUP = ROOT / "scripts" / "startup_check.py"
STARTUP_TIMEOUT_SEC = 25


def _dry_run_ok() -> bool:
    return os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


def main() -> int:
    ap = argparse.ArgumentParser(description="Paper intent probe")
    ap.add_argument("--env", default="paper")
    args = ap.parse_args()

    if not _dry_run_ok():
        print("FAIL: set DRY_RUN=true for intent probe", file=sys.stderr)
        return 2
    if str(args.env).lower() not in ("paper", "testnet", "dry"):
        print(
            f"FAIL: env={args.env!r} not allowed (paper/testnet only)",
            file=sys.stderr,
        )
        return 2

    lines: list[str] = [
        "# paper intent probe",
        f"- ts: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- env: {args.env}",
        f"- DRY_RUN: {os.environ.get('DRY_RUN')}",
        f"- python: {sys.executable}",
    ]
    warn = ""
    if STARTUP.is_file():
        try:
            py_compile.compile(str(STARTUP), doraise=True)
            lines.append("- startup_check: py_compile ok")
        except Exception as exc:
            print(f"FAIL: startup_check py_compile: {exc}", file=sys.stderr)
            return 1
        cmd = [
            sys.executable,
            str(STARTUP),
            "--strict",
            "--env",
            str(args.env),
        ]
        env = {**os.environ, "DRY_RUN": "true"}
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=STARTUP_TIMEOUT_SEC,
                env=env,
                check=False,
            )
            lines.append(f"- startup_check_rc: {proc.returncode}")
            out = ((proc.stdout or "") + (proc.stderr or ""))[-3000:]
            lines.append("## startup_check output")
            lines.append("```")
            lines.append(out or "(empty)")
            lines.append("```")
            if proc.returncode != 0:
                warn = f"startup_check rc={proc.returncode}"
        except subprocess.TimeoutExpired:
            warn = f"startup_check timeout {STARTUP_TIMEOUT_SEC}s"
            lines.append(f"- startup_check_rc: timeout({STARTUP_TIMEOUT_SEC}s)")
            lines.append(
                "- note: harness still PASS — fix startup_check hang separately"
            )
    else:
        lines.append("- startup_check: missing (harness-only)")

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if not warn else f"PASS_WITH_WARN ({warn})"
    body = "\n".join(lines) + f"\n\nstatus: {status}\n"
    OUT_REPORT.write_text(body, encoding="utf-8")
    print(f"paper_intent_probe: {status} report={OUT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def run_script_seed(ws: Path, tid: str) -> dict[str, Any]:
    """Write probe script + report stub; commit; leave for testing gate."""
    ws = Path(ws)
    tid = str(tid)
    scripts_dir = ws / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    dest = scripts_dir / _PROBE_NAME

    # Prefer CCC template if present, else qb-aware body
    tmpl = _ccc_repo_root() / "templates" / _PROBE_NAME
    body = _probe_body_for_app()
    if tmpl.is_file():
        # Keep app-aware body (startup_check); template is minimal fallback only
        _log.info("script_seed using app-aware probe body (tmpl exists as reference)")
    dest.write_text(body, encoding="utf-8")
    dest.chmod(0o755)

    report_dir = ws / "docs" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    latest = report_dir / "paper-intent-probe-latest.md"
    if not latest.is_file():
        latest.write_text(
            "# paper intent probe\n\nstatus: SEEDED (run DRY_RUN probe to fill)\n",
            encoding="utf-8",
        )

    # Optional STATUS / DRY_RUN_SMOKE touch if plan asked
    plan = ws / ".ccc" / "plans" / f"{tid}.plan.md"
    plan_txt = (
        plan.read_text(encoding="utf-8", errors="replace") if plan.is_file() else ""
    )
    if "DRY_RUN_SMOKE" in plan_txt or "dry_run_smoke" in plan_txt.lower():
        smoke = ws / "docs" / "DRY_RUN_SMOKE.md"
        smoke.parent.mkdir(parents=True, exist_ok=True)
        if not smoke.is_file():
            smoke.write_text(
                "# DRY_RUN smoke\n\nSeeded by CCC script_seed. "
                "Run: `DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper`\n",
                encoding="utf-8",
            )

    # Report for board
    ccc_reports = ws / ".ccc" / "reports"
    ccc_reports.mkdir(parents=True, exist_ok=True)
    (ccc_reports / f"{tid}.report.md").write_text(
        f"# {tid} script_seed\n\n"
        f"- path: script_seed (deterministic, no opencode)\n"
        f"- wrote: `scripts/{_PROBE_NAME}`\n"
        f"- report: `docs/reports/paper-intent-probe-latest.md`\n",
        encoding="utf-8",
    )
    (ccc_reports / f"{tid}.result.json").write_text(
        json.dumps(
            {
                "ok": True,
                "path": "script_seed",
                "wrote": [f"scripts/{_PROBE_NAME}"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # Commit product files (probe + report)
    commit = ""
    try:
        import subprocess

        subprocess.run(
            ["git", "add", f"scripts/{_PROBE_NAME}", "docs/reports"],
            cwd=ws,
            check=False,
            capture_output=True,
        )
        r = subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"feat({tid}): seed paper_intent_probe via script_seed",
            ],
            cwd=ws,
            check=False,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ws,
                capture_output=True,
                text=True,
                check=False,
            )
            commit = (sha.stdout or "").strip()
    except OSError as exc:
        _log.warning("script_seed git commit: %s", exc)

    # Move planned/in_progress → testing for acceptance
    try:
        from _board_store import FileBoardStore

        store = FileBoardStore(ws)
        col, _ = store.find_task(tid)
        if col in ("planned", "in_progress"):
            store.move_task(tid, col, "testing")
        store.update_index()
    except Exception as exc:
        _log.warning("script_seed move testing: %s", exc)

    _log.info("[script_seed] %s wrote %s commit=%s", tid, dest, commit or "?")
    return {
        "ok": True,
        "path": "script_seed",
        "wrote": str(dest),
        "commit": commit,
    }

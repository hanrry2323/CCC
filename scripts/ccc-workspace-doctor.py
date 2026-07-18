#!/usr/bin/env python3
"""ccc-workspace-doctor — 多仓登记卫生检查（v0.50）

Usage:
  python3 scripts/ccc-workspace-doctor.py              # doctor（默认）
  python3 scripts/ccc-workspace-doctor.py list
  python3 scripts/ccc-workspace-doctor.py prune [--apply]
  python3 scripts/ccc-workspace-doctor.py register <path> [--name NAME]
  python3 scripts/ccc-workspace-doctor.py unregister <path|name>

Exit 1 if any ERROR on doctor.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _workspace_registry import (  # noqa: E402
    REGISTRY_FILE,
    is_ephemeral_path,
    list_registered_entries,
    prune_missing,
    register_workspace,
    unregister_workspace,
)

ACTIVE_COLS = ("backlog", "planned", "in_progress", "testing", "abnormal")


def _task_visible(path: Path) -> bool:
    """False if ui_hidden or missing/unreadable."""
    try:
        line = path.read_text(encoding="utf-8").splitlines()[0]
        t = json.loads(line)
    except (OSError, json.JSONDecodeError, IndexError):
        return True
    return not bool(t.get("ui_hidden"))


def _board_counts(root: Path) -> dict[str, int]:
    board = root / ".ccc" / "board"
    out: dict[str, int] = {}
    if not board.is_dir():
        return out
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        d = board / col
        if not d.is_dir():
            out[col] = 0
            continue
        out[col] = sum(
            1 for p in d.glob("*.jsonl") if p.is_file() and _task_visible(p)
        )
    return out


def _agent_docs(root: Path) -> str:
    bits = []
    if (root / "CLAUDE.md").is_file():
        bits.append("CLAUDE")
    elif (root / ".claude" / "CLAUDE.md").is_file():
        bits.append(".claude/CLAUDE")
    if (root / "AGENTS.md").is_file():
        bits.append("AGENTS")
    if (root / ".ccc" / "profile.md").is_file():
        bits.append("profile")
    if (root / ".ccc" / "state.md").is_file():
        bits.append("state")
    return ",".join(bits) if bits else "NONE"


def _discover_board_paths() -> dict[str, Path]:
    """Best-effort mirror of board-server discover (program + projects)."""
    found: dict[str, Path] = {}
    roots = [Path.home() / "program", Path.home() / "program" / "projects"]
    for base in roots:
        if not base.is_dir():
            continue
        try:
            children = sorted(base.iterdir())
        except OSError:
            continue
        for p in children:
            if not p.is_dir():
                continue
            if not (p / ".ccc" / "board").is_dir():
                continue
            found[p.name] = p.resolve()
    return found


def cmd_list(_: argparse.Namespace) -> int:
    entries = list_registered_entries()
    print(json.dumps({"registry": str(REGISTRY_FILE), "workspaces": entries}, indent=2))
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    result = prune_missing(dry_run=not args.apply)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    out = register_workspace(args.path, name=args.name)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def cmd_unregister(args: argparse.Namespace) -> int:
    out = unregister_workspace(args.target)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def cmd_doctor(_: argparse.Namespace) -> int:
    entries = list_registered_entries()
    discovered = _discover_board_paths()
    reg_paths = {e["path"] for e in entries}
    disc_paths = {str(p) for p in discovered.values()}

    rows: list[dict] = []
    errors = 0
    warns = 0

    for e in entries:
        root = Path(e["path"])
        errs: list[str] = []
        warnings: list[str] = []
        if is_ephemeral_path(root):
            errs.append("ephemeral")
        if not root.is_dir():
            errs.append("missing")
        elif not (root / ".ccc" / "board").is_dir():
            errs.append("no_board")
        docs = _agent_docs(root) if root.is_dir() else "—"
        if docs == "NONE":
            errs.append("no_agent_docs")
        elif "CLAUDE" not in docs and ".claude/CLAUDE" not in docs and "AGENTS" not in docs:
            warnings.append("weak_agent_docs")
        counts = _board_counts(root) if root.is_dir() else {}
        active = sum(counts.get(c, 0) for c in ACTIVE_COLS)
        # done epic visible?
        backlog_dir = root / ".ccc" / "board" / "backlog"
        stuck_done = 0
        if backlog_dir.is_dir():
            for f in backlog_dir.glob("*.jsonl"):
                try:
                    t = json.loads(f.read_text(encoding="utf-8").splitlines()[0])
                except (OSError, json.JSONDecodeError, IndexError):
                    continue
                if (
                    t.get("card_kind") == "epic"
                    and t.get("split_status") == "done"
                    and not t.get("ui_hidden")
                ):
                    stuck_done += 1
        if stuck_done:
            warnings.append(f"done_epic_visible={stuck_done}")

        if errs:
            errors += 1
        if warnings:
            warns += 1

        rows.append(
            {
                "name": e["name"],
                "path": e["path"],
                "engine": True,
                "board_active": active,
                "counts": counts,
                "agent_docs": docs,
                "errors": errs,
                "warnings": warnings,
            }
        )

    # Board-visible but not registered
    for name, path in sorted(discovered.items()):
        key = str(path)
        if key in reg_paths:
            continue
        warns += 1
        rows.append(
            {
                "name": name,
                "path": key,
                "engine": False,
                "board_active": sum(_board_counts(path).get(c, 0) for c in ACTIVE_COLS),
                "counts": _board_counts(path),
                "agent_docs": _agent_docs(path),
                "errors": [],
                "warnings": ["hub_visible_not_in_engine_registry"],
            }
        )

    # Registered but not under discover roots (OK for CCC outside scan) — info only
    fleet_n = len(entries)
    if fleet_n > 10:
        errors += 1
        fleet_warn = ["fleet_over_10"]
    else:
        fleet_warn = []

    print(f"registry: {REGISTRY_FILE}")
    print(f"registered: {fleet_n}  discovered_extra: {len(disc_paths - reg_paths)}")
    if fleet_warn:
        print(f"FLEET ERROR: {fleet_warn}")
    print()
    hdr = f"{'name':<16} {'eng':<4} {'active':>6} {'docs':<28} status"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        status = ""
        if r["errors"]:
            status = "ERROR " + ",".join(r["errors"])
        elif r["warnings"]:
            status = "WARN " + ",".join(r["warnings"])
        else:
            status = "OK"
        print(
            f"{r['name']:<16} {str(r['engine']):<4} {r['board_active']:>6} "
            f"{r['agent_docs']:<28} {status}"
        )

    print()
    print(f"summary: errors={errors} warnings={warns}")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CCC workspace fleet doctor")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("doctor", help="health check (default)")
    sub.add_parser("list", help="dump registry JSON")

    p_prune = sub.add_parser("prune", help="remove dead/ephemeral entries")
    p_prune.add_argument("--apply", action="store_true", help="write changes")

    p_reg = sub.add_parser("register", help="register a workspace")
    p_reg.add_argument("path")
    p_reg.add_argument("--name", default=None)

    p_un = sub.add_parser("unregister", help="unregister by path or name")
    p_un.add_argument("target")

    args = p.parse_args(argv)
    cmd = args.cmd or "doctor"
    if cmd == "doctor":
        return cmd_doctor(args)
    if cmd == "list":
        return cmd_list(args)
    if cmd == "prune":
        return cmd_prune(args)
    if cmd == "register":
        return cmd_register(args)
    if cmd == "unregister":
        return cmd_unregister(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

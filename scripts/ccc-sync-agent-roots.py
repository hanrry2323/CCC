#!/usr/bin/env python3
"""ccc-sync-agent-roots — 把舰队登记同步到 Claude / OpenCode 根目录白名单。

从 ~/.ccc/workspaces.json 生成：
  - 优先 ~/.ccc/loop-code/settings.json（M1 Desktop / Phase5）
  - 兼容：若存在 ~/.claude/settings.json 也同步（2017 / 个人残留）
  - ~/.ccc/engine-claude/settings.json（若 Engine 配置家存在）
  - ~/.config/opencode/opencode.json → mcp.filesystem 多根路径

额外固定根：配置家自身、~/.ccc、/tmp；OpenCode 仅舰队路径。

Usage:
  python3 scripts/ccc-sync-agent-roots.py           # apply
  python3 scripts/ccc-sync-agent-roots.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

REGISTRY = HOME / ".ccc" / "workspaces.json"
LOOP_CODE_SETTINGS = HOME / ".ccc" / "loop-code" / "settings.json"
ENGINE_SETTINGS = HOME / ".ccc" / "engine-claude" / "settings.json"
CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
OPENCODE_CONFIG = HOME / ".config" / "opencode" / "opencode.json"
WORKFLOW_MD = HOME / ".config" / "opencode" / "instructions" / "workflow.md"

CLAUDE_EXTRA = [
    str(HOME / ".ccc"),
    "/tmp",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_fleet_paths() -> list[str]:
    if not REGISTRY.is_file():
        return []
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out: list[str] = []
    seen: set[str] = set()
    for item in data.get("workspaces") or []:
        raw = item if isinstance(item, str) else (item.get("path") if isinstance(item, dict) else None)
        if not raw:
            continue
        p = str(Path(str(raw)).expanduser().resolve())
        if p in seen:
            continue
        if not Path(p).is_dir():
            continue
        seen.add(p)
        out.append(p)
    return sorted(out)


def backup(path: Path) -> Path | None:
    if not path.is_file():
        return None
    bak = path.with_suffix(path.suffix + f".bak.{_now()}")
    shutil.copy2(path, bak)
    return bak


def _sync_one_settings(path: Path, fleet: list[str], *, dry_run: bool, label: str) -> list[str]:
    extra = list(CLAUDE_EXTRA)
    extra.insert(0, str(path.parent))
    roots = list(dict.fromkeys(extra + fleet))
    if dry_run:
        print(f"dry-run {label}: {path} → {len(roots)} roots")
        return roots
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        backup(path)
    else:
        data = {"permissions": {"defaultMode": "bypassPermissions", "additionalDirectories": []}}
    perms = data.setdefault("permissions", {})
    old = list(perms.get("additionalDirectories") or [])
    perms["additionalDirectories"] = roots
    if "defaultMode" not in perms:
        perms["defaultMode"] = "bypassPermissions"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{label} additionalDirectories: {len(old)} → {len(roots)} ({path})")
    return roots


def sync_claude(fleet: list[str], *, dry_run: bool) -> list[str]:
    """M1 优先 loop-code；engine-claude / 个人 ~/.claude 兼容同步。"""
    from _claude_cli import ensure_engine_claude_config_dir, ensure_loop_code_config_dir

    ensure_loop_code_config_dir(LOOP_CODE_SETTINGS.parent)
    roots = _sync_one_settings(
        LOOP_CODE_SETTINGS, fleet, dry_run=dry_run, label="loop-code"
    )
    # Engine 家：本机若跑 Engine 或 2017 会有此目录
    ensure_engine_claude_config_dir(ENGINE_SETTINGS.parent)
    _sync_one_settings(
        ENGINE_SETTINGS, fleet, dry_run=dry_run, label="engine-claude"
    )
    if CLAUDE_SETTINGS.is_file():
        _sync_one_settings(
            CLAUDE_SETTINGS, fleet, dry_run=dry_run, label="~/.claude"
        )
    return roots


def sync_opencode(fleet: list[str], *, dry_run: bool) -> list[str]:
    if not OPENCODE_CONFIG.is_file():
        print(f"skip opencode: missing {OPENCODE_CONFIG}")
        return []
    data = json.loads(OPENCODE_CONFIG.read_text(encoding="utf-8"))
    mcp = data.setdefault("mcp", {})
    fs = mcp.setdefault("filesystem", {})
    cmd = [
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        *fleet,
    ]
    if dry_run:
        return fleet
    backup(OPENCODE_CONFIG)
    fs["command"] = cmd
    fs["enabled"] = True
    fs["type"] = "local"
    comp = data.setdefault("compaction", {})
    if int(comp.get("preserve_recent_tokens") or 0) > 120000:
        comp["preserve_recent_tokens"] = 120000
    OPENCODE_CONFIG.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"opencode filesystem roots: {len(fleet)}")
    return fleet


def ensure_workflow(*, dry_run: bool) -> None:
    if WORKFLOW_MD.is_file():
        return
    if dry_run:
        print(f"would create {WORKFLOW_MD}")
        return
    WORKFLOW_MD.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW_MD.write_text(
        """# OpenCode workflow (CCC fleet)

- Prefer `--dir <workspace>` and `--pure` for automation (CCC Engine default).
- Filesystem MCP roots are synced from `~/.ccc/workspaces.json` via `ccc-sync-agent-roots.py`.
- Do not commit to CCC orchestrator when working on a business workspace.
- Empty board + invent hard-off = idle is normal.
""",
        encoding="utf-8",
    )
    print(f"created {WORKFLOW_MD}")


def untrust_users_root(*, dry_run: bool) -> None:
    """Clear accidental trust of filesystem root /Users in ~/.claude.json."""
    path = HOME / ".claude.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    projects = data.get("projects")
    if not isinstance(projects, dict):
        return
    entry = projects.get("/Users")
    if not isinstance(entry, dict):
        return
    if entry.get("hasTrustDialogAccepted") is not True:
        return
    if dry_run:
        print("would set /Users hasTrustDialogAccepted=false")
        return
    backup(path)
    entry["hasTrustDialogAccepted"] = False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("untrusted /Users in ~/.claude.json")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    fleet = load_fleet_paths()
    if not fleet:
        print("ERROR: empty fleet from", REGISTRY)
        return 1
    print("fleet:", *fleet, sep="\n  ")
    sync_claude(fleet, dry_run=args.dry_run)
    sync_opencode(fleet, dry_run=args.dry_run)
    ensure_workflow(dry_run=args.dry_run)
    untrust_users_root(dry_run=args.dry_run)
    if args.dry_run:
        print("dry-run OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

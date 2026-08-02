#!/usr/bin/env python3
"""migrate-desktop-conversation-bind.py — 旧 UUID thread → {projectId}::main

用法:
  python3 scripts/migrate-desktop-conversation-bind.py --dry-run
  python3 scripts/migrate-desktop-conversation-bind.py --apply
  python3 scripts/migrate-desktop-conversation-bind.py --apply --chat-dir /path/to/.ccc/chat

做两件事（不碰 Board 任务文件）:
1. 改写 `_desktop/<project>/epic_history.json` 与 `last_epic.json` 的 thread_id → `{project}::main`
2. 合并同项目下非 `::main` 的 session JSON 消息进 `{project}::main.json`，源文件改名为 `.migrated`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _conversation_id(project_id: str) -> str:
    return f"{project_id}::main"


def _load_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(path: Path, data: Any, *, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _message_score(messages: list) -> int:
    if not isinstance(messages, list):
        return 0
    body = 0
    tools = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        body += len(str(m.get("content") or ""))
        steps = m.get("tool_steps") or m.get("toolSteps") or []
        if isinstance(steps, list):
            tools += len(steps)
    return len(messages) * 1000 + body + tools * 50


def migrate_epic_bind(project_id: str, desktop_dir: Path, *, dry_run: bool) -> dict[str, int]:
    stats = {"history_rewritten": 0, "last_rewritten": 0}
    conv = _conversation_id(project_id)
    hist = desktop_dir / "epic_history.json"
    raw = _load_json(hist)
    if isinstance(raw, list):
        changed = False
        for item in raw:
            if not isinstance(item, dict) or not item.get("epic_id"):
                continue
            old = str(item.get("thread_id") or "").strip()
            if old != conv:
                item["thread_id"] = conv
                changed = True
                stats["history_rewritten"] += 1
        if changed:
            _write_json(hist, raw, dry_run=dry_run)

    last_path = desktop_dir / "last_epic.json"
    last = _load_json(last_path)
    if isinstance(last, dict) and last.get("epic_id"):
        old = str(last.get("thread_id") or "").strip()
        if old != conv:
            last["thread_id"] = conv
            stats["last_rewritten"] += 1
            _write_json(last_path, last, dry_run=dry_run)
    return stats


def migrate_sessions(project_id: str, project_chat: Path, *, dry_run: bool) -> dict[str, int]:
    stats = {"sessions_merged": 0, "messages_added": 0}
    if not project_chat.is_dir():
        return stats
    conv = _conversation_id(project_id)
    # session 文件名可能含 `:` → `{project}::main.json`
    main_name = f"{conv}.json"
    main_path = project_chat / main_name
    main = _load_json(main_path)
    if not isinstance(main, dict):
        main = {
            "session_id": conv,
            "project": project_id,
            "messages": [],
            "title": "对话",
        }
    main_msgs = list(main.get("messages") or [])
    if not isinstance(main_msgs, list):
        main_msgs = []

    for path in sorted(project_chat.glob("*.json")):
        if path.name in {"_index.json", main_name}:
            continue
        if path.name.endswith(".migrated"):
            continue
        stem = path.stem
        if stem.endswith("::main") or stem == conv:
            continue
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        msgs = data.get("messages") or []
        if not isinstance(msgs, list) or not msgs:
            # 空会话：仍归档
            dest = path.with_suffix(path.suffix + ".migrated")
            if dry_run:
                print(f"  [dry-run] rename {path.name} -> {dest.name}")
            else:
                path.rename(dest)
            stats["sessions_merged"] += 1
            continue
        # 合并：按时间粗排，较长优先不丢
        for m in msgs:
            if isinstance(m, dict):
                main_msgs.append(m)
                stats["messages_added"] += 1
        dest = path.with_suffix(path.suffix + ".migrated")
        if dry_run:
            print(f"  [dry-run] merge {path.name} ({len(msgs)} msgs) -> {main_name}")
            print(f"  [dry-run] rename {path.name} -> {dest.name}")
        else:
            path.rename(dest)
        stats["sessions_merged"] += 1

    main["session_id"] = conv
    main["project"] = project_id
    main["messages"] = main_msgs
    if stats["sessions_merged"] or stats["messages_added"] or not main_path.is_file():
        # 仅在有变更或主会话不存在时写
        if stats["sessions_merged"] or not main_path.is_file():
            _write_json(main_path, main, dry_run=dry_run)
    return stats


def migrate_chat_dir(chat_dir: Path, *, dry_run: bool) -> None:
    desktop_root = chat_dir / "_desktop"
    projects: set[str] = set()
    if desktop_root.is_dir():
        for p in desktop_root.iterdir():
            if p.is_dir() and not p.name.startswith("_"):
                projects.add(p.name)
    for p in chat_dir.iterdir():
        if p.is_dir() and p.name not in {"_desktop", "_trash"} and not p.name.startswith("."):
            projects.add(p.name)

    print(f"chat_dir={chat_dir} projects={len(projects)} dry_run={dry_run}")
    total_h = total_s = 0
    for pid in sorted(projects):
        print(f"* {pid}")
        dstat = migrate_epic_bind(pid, desktop_root / pid, dry_run=dry_run)
        sstat = migrate_sessions(pid, chat_dir / pid, dry_run=dry_run)
        total_h += dstat["history_rewritten"] + dstat["last_rewritten"]
        total_s += sstat["sessions_merged"]
        print(f"  epic_bind={dstat} sessions={sstat}")
    print(f"done: epic_fields_rewritten≈{total_h} sessions_merged={total_s}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="写入变更（默认 dry-run）")
    ap.add_argument(
        "--chat-dir",
        type=Path,
        default=None,
        help="Hub CHAT_DIR（默认读 chat_server.config.CHAT_DIR）",
    )
    ap.add_argument("--dry-run", action="store_true", help="显式 dry-run（默认）")
    args = ap.parse_args()
    dry_run = not args.apply
    if args.chat_dir:
        chat_dir = args.chat_dir.expanduser().resolve()
    else:
        from chat_server import config

        chat_dir = Path(config.CHAT_DIR)
    migrate_chat_dir(chat_dir, dry_run=dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

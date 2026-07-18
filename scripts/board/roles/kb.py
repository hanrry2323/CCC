"""board.roles.kb — extracted from ccc-board.py (behavior-preserving)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import uuid
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from _config import Config, get_logger, parse_duration
from _executor import _claude_env, _sanitized_env
from _board_store import FileBoardStore, _atomic_write as _store_atomic_write
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id
from _utils import sanitize_prompt_input as _sanitize_prompt_input
from _claude_cli import ClaudeCliMissing, resolve_claude_cli
import phase_lint

from board.context import get_workspace, set_workspace, board_dir, ccc_home
from board.lock import (
    acquire_named_lock as _acquire_product_lock,
    release_named_lock as _release_product_lock,
)
from board.prompt import build_dev_phase_prompt
from board.phase import (
    _load_phases,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _current_running_phase,
    _mark_phase_done,
    _mark_phase_failed,
    _check_phase_failures,
    _move_task_to_abnormal_if_all_terminal_failed,
)
from board.roles.common import (
    cfg,
    store,
    _log,
    CCC_HOME,
    MAX_RETRY,
    MAX_STALE_HOURS,
    sanitize_id,
    now_iso,
    _quarantine,
    list_tasks,
    move_task,
    create_task,
    update_index,
    _get_cfg,
    _get_store,
    _reset_lazy,
    _backoff_seconds,
    _load_timeout,
    _load_retry_cap,
    _load_retry_from_phases,
    _claude_bin,
    _get_relay_url,
    WORKSPACES,
)

def _extract_agents_suggestions(
    filepath: Path, task_id: str, source: str
) -> list[dict]:
    """从 report/verdict 文件中提取 AGENTS.md 建议"""
    import re

    suggestions = []
    if not filepath.exists():
        return suggestions
    content = filepath.read_text()
    # tempered dot: match content until blank line, ---, next marker, or end
    pattern = re.compile(
        r"> \*\*AGENTS\.md 建议:\*\*\s*((?:(?!> \*\*AGENTS\.md 建议:|\n\n|\n---).)*)",
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        text = match.group(1).strip()
        text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
        text = text.strip()
        if text:
            suggestions.append({"task_id": task_id, "source": source, "content": text})
    return suggestions


def kb_role() -> dict:
    """知识管理员: 扫 verified → 归档 + git tag → 挪 released → 收集 AGENTS.md 建议"""
    import subprocess as sp

    moved = []
    all_suggestions: list[dict] = []
    for task in list_tasks("verified"):
        task_id = task["id"]

        # ── Step 1: 版本 bump + CHANGELOG ──
        try:
            new_ver = _bump_version(get_workspace())
            _append_changelog(get_workspace(), task_id, new_ver)
        except Exception as exc:
            _log.warning("version bump failed, skipping tag: %s", exc)
            new_ver = "unknown"

        # ── Step 2: git tag v{version} ──
        if new_ver != "unknown":
            sp.run(
                [
                    "git",
                    "tag",
                    "-a",
                    new_ver,
                    "-m",
                    f"{new_ver}: {task_id} 发布",
                ],
                cwd=get_workspace(),
                capture_output=True,
                timeout=10,
            )
            push_r = sp.run(
                ["git", "push", "origin", new_ver],
                cwd=get_workspace(),
                capture_output=True,
                timeout=30,
            )
            if push_r.returncode != 0:
                # v0.38: push 失败不阻断本地 released（避免永久卡 verified）
                _log.error(
                    "[kb] %s push tag 失败 rc=%s（仍挪 released，本地 tag 已建）",
                    task_id,
                    push_r.returncode,
                )
                fail_log = (
                    get_workspace() / ".ccc" / "reports" / f"{task_id}.push-fail.md"
                )
                fail_log.write_text(
                    f"# {task_id} push tag 失败\n\n"
                    f"rc={push_r.returncode}\n"
                    f"{(push_r.stderr or b'').decode('utf-8', errors='replace')[:500]}\n"
                )

        # ── Step 3: 收集 AGENTS.md 建议 ──
        report_file = get_workspace() / ".ccc" / "reports" / f"{task_id}.report.md"
        all_suggestions.extend(
            _extract_agents_suggestions(report_file, task_id, source="dev")
        )
        verdict_file = get_workspace() / ".ccc" / "verdicts" / f"{task_id}.verdict.md"
        all_suggestions.extend(
            _extract_agents_suggestions(verdict_file, task_id, source="reviewer")
        )

        # ── Step 4: 挪 released ──
        move_task(task_id, "verified", "released")
        moved.append(task_id)

    # 去重 → 写 pending-agents-suggestions.md
    if all_suggestions:
        seen: set[str] = set()
        unique: list[dict] = []
        for s in all_suggestions:
            key = s["content"].strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(s)

        pending_file = get_workspace() / ".ccc" / "pending-agents-suggestions.md"
        template_file = get_workspace() / "templates" / "pending-agents-suggestions.md"

        new_blocks: list[str] = []
        now_str = now_iso()[:10]
        for s in unique:
            block = (
                f"## 来源 task: {s['task_id']}\n\n"
                f"归档日期: {now_str}\n\n"
                f"### 来自 {s['source']}\n\n"
                f"{s['content']}\n\n"
                f"---\n"
            )
            new_blocks.append(block)

        new_content = "\n".join(new_blocks)
        if pending_file.exists():
            existing = pending_file.read_text().rstrip()
            pending_file.write_text(existing + "\n" + new_content + "\n")
        else:
            header = (
                template_file.read_text()
                if template_file.exists()
                else "# Pending AGENTS.md Suggestions\n\n"
            )
            pending_file.write_text(header + "\n" + new_content + "\n")
        _log.info("[kb] ✓ 收集 {len(unique)} 条 AGENTS.md 建议到 %s", pending_file)

    return {
        "role": "kb",
        "moved": moved,
        "suggestions_collected": len(all_suggestions),
        "counts": update_index(),
    }


def _bump_version(ws_path: Path) -> str:
    """读取 VERSION 文件，bump patch version，写回。返回新版本号。"""
    version_file = ws_path / "VERSION"
    if not version_file.exists():
        new_version = "v0.0.1"
        version_file.write_text(new_version)
        return new_version
    current = version_file.read_text().strip()
    m = re.match(r"^(v?)(\d+)\.(\d+)\.(\d+)$", current, re.IGNORECASE)
    if not m:
        return current
    prefix = m.group(1) or "v"
    major, minor, patch = int(m.group(2)), int(m.group(3)), int(m.group(4))
    new_version = f"{prefix}{major}.{minor}.{patch + 1}"
    version_file.write_text(new_version)
    return new_version


def _append_changelog(ws_path: Path, tid: str, new_version: str) -> None:
    """在 CHANGELOG.md 最旧版本条目之上插入新条目。"""
    changelog_path = ws_path / "CHANGELOG.md"
    today_str = now_iso()[:10]
    entry = f"\n## [{new_version}] — {today_str}\n\n- {tid}: 看板发布\n"
    if changelog_path.exists():
        text = changelog_path.read_text()
    else:
        text = "# Changelog — CCC\n\n"
    # 在最旧 ## [v...] 条目之上插入（第一个版本标题之后）
    m = re.search(r"\n## \[v", text)
    if m:
        insert_at = m.start()
        new_text = text[:insert_at] + entry + text[insert_at:]
    else:
        new_text = text.rstrip() + entry + "\n"
    if tid in new_text and new_version in text:
        return
    changelog_path.write_text(new_text)
    # git commit VERSION + CHANGELOG（仅有改动时）
    try:
        check = subprocess.run(
            ["git", "diff", "--quiet", "VERSION", "CHANGELOG.md"],
            cwd=ws_path,
            capture_output=True,
            env=_sanitized_env(),
        )
        if check.returncode != 0:
            subprocess.run(
                ["git", "add", "VERSION", "CHANGELOG.md"],
                cwd=ws_path,
                capture_output=True,
                timeout=10,
                env=_sanitized_env(),
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"chore: bump {new_version} ({tid})",
                ],
                cwd=ws_path,
                capture_output=True,
                timeout=30,
                env=_sanitized_env(),
            )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.warning("changelog git commit failed (non-blocking): %s", exc)


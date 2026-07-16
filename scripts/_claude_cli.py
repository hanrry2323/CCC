"""_claude_cli.py — 解析 claude CLI 绝对路径（v0.40.1）

launchd / sanitized env 的 PATH 往往不含 ~/.local/bin，
导致 Popen(['claude']) → Errno 2。必须解析为绝对路径。
"""

from __future__ import annotations

import os
from pathlib import Path
from shutil import which
from typing import Optional


class ClaudeCliMissing(RuntimeError):
    """claude CLI 不可用。"""


def _extra_path_dirs() -> list[str]:
    return [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / ".npm-global" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]


def _candidates() -> list[Path]:
    return [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("/opt/homebrew/bin/claude"),
        Path("/usr/local/bin/claude"),
    ]


def claude_path_prefixes() -> list[str]:
    """供 _sanitized_env 拼 PATH 的目录列表。"""
    return [d for d in _extra_path_dirs() if Path(d).is_dir()]


def resolve_claude_cli(*, require: bool = True) -> Optional[str]:
    """返回 claude 可执行绝对路径。

    优先级: CCC_CLAUDE_BIN → PATH which（扩 PATH）→ 固定候选。
    require=True 且找不到时抛 ClaudeCliMissing。
    """
    env_bin = (os.environ.get("CCC_CLAUDE_BIN") or "").strip()
    if env_bin:
        p = Path(env_bin).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p.resolve())
        w = which(env_bin)
        if w:
            return w

    # Expand PATH for which()
    old_path = os.environ.get("PATH", "")
    extras = [d for d in _extra_path_dirs() if d not in old_path.split(":")]
    if extras:
        os.environ["PATH"] = ":".join(extras + [old_path]) if old_path else ":".join(extras)
    try:
        w = which("claude")
        if w and Path(w).is_file():
            return w
    finally:
        if extras:
            os.environ["PATH"] = old_path

    for cand in _candidates():
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand.resolve())

    if require:
        raise ClaudeCliMissing(
            "claude CLI not found. Set CCC_CLAUDE_BIN or install to "
            "~/.local/bin/claude"
        )
    return None

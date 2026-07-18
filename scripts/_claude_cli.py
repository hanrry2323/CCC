"""_claude_cli.py — 解析 Claude 兼容 CLI 绝对路径（v0.40.1+ / executor 可插拔）

launchd / sanitized env 的 PATH 往往不含 ~/.local/bin，
导致 Popen(['claude']) → Errno 2。必须解析为绝对路径。

优先级（对话 CLI）:
  1. CCC_CLAUDE_BIN（显式绝对/相对路径或 PATH 名）
  2. CCC_EXECUTOR=loop-code → <CCC_HOME>/vendor/loop-code/cli
  3. PATH which('claude')（扩 PATH）
  4. 固定候选路径
"""

from __future__ import annotations

import os
from pathlib import Path
from shutil import which
from typing import Optional


class ClaudeCliMissing(RuntimeError):
    """claude / loop-code CLI 不可用。"""


def ccc_home() -> Path:
    """CCC 仓根（本文件在 scripts/）。"""
    return Path(__file__).resolve().parents[1]


def loop_code_cli_path() -> Path:
    return ccc_home() / "vendor" / "loop-code" / "cli"


def _extra_path_dirs() -> list[str]:
    dirs = [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / ".npm-global" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    # Prefer vendor dir on PATH when present (does not select it unless which/loop-code)
    vendor_bin = str(loop_code_cli_path().parent)
    if Path(vendor_bin).is_dir():
        dirs.insert(0, vendor_bin)
    return dirs


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


def _is_executable(p: Path) -> bool:
    try:
        return p.is_file() and os.access(p, os.X_OK)
    except OSError:
        return False


def _executor_wants_loop_code() -> bool:
    return (os.environ.get("CCC_EXECUTOR") or "").strip().lower() in (
        "loop-code",
        "loopcode",
        "loop_code",
    )


def resolve_claude_cli(*, require: bool = True) -> Optional[str]:
    """返回 Claude 兼容 CLI 可执行绝对路径。

    require=True 且找不到时抛 ClaudeCliMissing。
    """
    env_bin = (os.environ.get("CCC_CLAUDE_BIN") or "").strip()
    if env_bin:
        p = Path(env_bin).expanduser()
        if _is_executable(p):
            return str(p.resolve())
        w = which(env_bin)
        if w:
            return w
        if require:
            raise ClaudeCliMissing(
                f"CCC_CLAUDE_BIN={env_bin!r} is not an executable file"
            )
        return None

    if _executor_wants_loop_code():
        lc = loop_code_cli_path()
        if _is_executable(lc):
            return str(lc.resolve())
        if require:
            raise ClaudeCliMissing(
                f"CCC_EXECUTOR=loop-code but missing executable: {lc}. "
                "Run scripts/install-executor-loop-code.sh"
            )
        return None

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
        if _is_executable(cand):
            return str(cand.resolve())

    if require:
        raise ClaudeCliMissing(
            "claude CLI not found. Set CCC_CLAUDE_BIN, or CCC_EXECUTOR=loop-code "
            "with vendor/loop-code/cli, or install to ~/.local/bin/claude"
        )
    return None

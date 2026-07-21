"""_claude_cli.py — 解析 Claude 兼容 CLI 绝对路径（v0.40.1+ / executor 可插拔）

launchd / sanitized env 的 PATH 往往不含 ~/.local/bin，
导致 Popen(['claude']) → Errno 2。必须解析为绝对路径。

优先级（对话 CLI，宽松 / Engine）:
  1. CCC_CLAUDE_BIN（显式绝对/相对路径或 PATH 名）
  2. CCC_EXECUTOR=loop-code → <CCC_HOME>/vendor/loop-code/cli
  3. PATH which('claude')（扩 PATH）
  4. 固定候选路径

严格模式（sidecar / CCC_EXECUTOR=loop-code 默认）:
  仅 vendor/loop-code/cli，或 CCC_CLAUDE_BIN 且路径含 loop-code；禁止 PATH 个人 claude。
  见 docs/product/loop-code-ownership-cut.md
"""

from __future__ import annotations

import os
from pathlib import Path
from shutil import which
from typing import Optional


class ClaudeCliMissing(RuntimeError):
    """claude / loop-code CLI 不可用。"""


_LOOP_CODE_CLAUDE_MD = """# CCC Desktop · loop-code 私有配置家

你是 **Desktop 对话面** 的产品/架构搭档（本机 sidecar → loop-code）。
帮用户定意图、定稿可下达的 epic；转任务后由 **Mac2017 Engine** 自动编排。
你不是 Hub 聊天窗口，不是 Engine 的 product/dev/reviewer。

禁止口径：flash 中转站、`:4000`、ai-loop-router。
身份 SSOT：CCC 仓 `docs/product/desktop-agent-identity.md`。
"""


def ccc_home() -> Path:
    """CCC 仓根（本文件在 scripts/）。"""
    return Path(__file__).resolve().parents[1]


def loop_code_cli_path() -> Path:
    return ccc_home() / "vendor" / "loop-code" / "cli"


def default_loop_code_config_dir() -> Path:
    """M1 sidecar 私有配置家（CLAUDE_CONFIG_DIR）。"""
    return Path.home() / ".ccc" / "loop-code"


def ensure_loop_code_config_dir(path: Path | None = None) -> Path:
    """创建私有配置家并种子短版 CLAUDE.md（已存在则不覆盖）。"""
    root = path or default_loop_code_config_dir()
    root.mkdir(parents=True, exist_ok=True)
    claude_md = root / "CLAUDE.md"
    if not claude_md.is_file():
        claude_md.write_text(_LOOP_CODE_CLAUDE_MD, encoding="utf-8")
    return root


def path_is_loop_code(bin_path: str | Path) -> bool:
    """路径是否指向 loop-code 二进制（禁止个人 claude 冒充）。"""
    try:
        resolved = str(Path(bin_path).expanduser().resolve()).replace("\\", "/")
    except OSError:
        resolved = str(bin_path).replace("\\", "/")
    return "loop-code" in resolved.lower()


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


def resolve_claude_cli(
    *,
    require: bool = True,
    executor_strict: bool | None = None,
) -> Optional[str]:
    """返回 Claude 兼容 CLI 可执行绝对路径。

    require=True 且找不到时抛 ClaudeCliMissing。
    executor_strict=True：只接受 loop-code；禁止 PATH 个人 claude。
    executor_strict=None：当 CCC_EXECUTOR=loop-code 时自动严格（sidecar 默认）。
    """
    if executor_strict is None:
        executor_strict = _executor_wants_loop_code()

    env_bin = (os.environ.get("CCC_CLAUDE_BIN") or "").strip()
    if env_bin:
        p = Path(env_bin).expanduser()
        resolved: Optional[str] = None
        if _is_executable(p):
            resolved = str(p.resolve())
        else:
            w = which(env_bin)
            if w:
                resolved = w
        if resolved:
            if executor_strict and not path_is_loop_code(resolved):
                if require:
                    raise ClaudeCliMissing(
                        f"CCC_CLAUDE_BIN={env_bin!r} is not loop-code "
                        f"(got {resolved!r}); sidecar forbids personal claude"
                    )
                return None
            return resolved
        if require:
            raise ClaudeCliMissing(
                f"CCC_CLAUDE_BIN={env_bin!r} is not an executable file"
            )
        return None

    if _executor_wants_loop_code() or executor_strict:
        lc = loop_code_cli_path()
        if _is_executable(lc):
            return str(lc.resolve())
        if require:
            raise ClaudeCliMissing(
                f"CCC_EXECUTOR=loop-code but missing executable: {lc}. "
                "Run scripts/install-executor-loop-code.sh"
            )
        return None

    # 宽松路径（Engine / 无 CCC_EXECUTOR）：Expand PATH for which()
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


def resolve_anthropic_model(requested: str | None = None) -> str:
    """逻辑名 flash/code → 上游真实 model id。

    直连 MiniMax Anthropic（ANTHROPIC_BASE_URL 含 minimaxi/minimax.chat）时，
    Claude/loop-code 的 `flash` 映射为 `MiniMax-M3`（可用 ANTHROPIC_MODEL 覆盖）。
    走 ai-loop-router 时保持 flash/code 逻辑名。
    """
    req = (requested or "").strip()
    if not req:
        req = (os.environ.get("ANTHROPIC_MODEL") or "flash").strip() or "flash"
    base = (os.environ.get("ANTHROPIC_BASE_URL") or "").lower()
    direct_minimax = "minimaxi.com" in base or "minimax.chat" in base
    if not direct_minimax:
        return req
    # 已是上游 id
    if req.lower().startswith("minimax"):
        return req
    if req.lower() in ("flash", "code", "haiku", "sonnet", "opus", "pro"):
        override = (os.environ.get("ANTHROPIC_MODEL") or "").strip()
        if override and override.lower() not in ("flash", "code", "haiku", "sonnet", "opus"):
            return override
        return "MiniMax-M3"
    return req

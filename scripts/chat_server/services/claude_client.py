"""Claude helpers for CCC Hub chat.

Streaming turns go through ClaudeSessionManager (ClaudeSDKClient continuous
sessions). This module no longer spawns per-turn `claude -p`.
"""

from __future__ import annotations

from pathlib import Path

from .. import config


def _get_project_context(project_id: str, projects: dict) -> str:
    proj = projects.get(project_id)
    if not proj:
        return ""
    claude_path = Path(proj["path"]) / "CLAUDE.md"
    home_claude = Path.home() / ".claude" / "CLAUDE.md"
    parts = []
    if claude_path.exists():
        parts.append(f"## Project {proj['name']}")
        parts.append(claude_path.read_text().strip())
    if home_claude.exists():
        parts.append("## Global Config")
        parts.append(home_claude.read_text().strip())
    ctx = "\n\n".join(parts)
    if len(ctx) > 4000:
        truncated_len = len(ctx) - 4000
        ctx = (
            ctx[:4000]
            + f"\n\n> ⚠️ 项目上下文过长，已截断 {truncated_len} 字符（仅保留前 4000 字符）"
        )
    return ctx


ALLOWED_MODELS = frozenset({"flash", "code", "sonnet", "opus", "haiku"})


def resolve_model(model: str | None) -> str:
    m = (model or "flash").strip().lower()
    return m if m in ALLOWED_MODELS else "flash"


def resolve_chat_timeouts(
    requested: int | None = None,
    *,
    idle_default: int | None = None,
    max_default: int | None = None,
) -> tuple[int, int]:
    """返回 (idle_timeout_s, max_timeout_s)。

    - idle：距上次 stdout 活动的静默上限（有输出则重置）
    - max：整轮墙钟硬上限
    requested：客户端传入的 timeout，当作 idle 意图并夹紧。
    """
    idle = int(idle_default if idle_default is not None else config.CHAT_IDLE_TIMEOUT)
    hard = int(max_default if max_default is not None else config.CHAT_MAX_TIMEOUT)
    if requested is not None:
        try:
            req = int(requested)
        except (TypeError, ValueError):
            req = idle
        # 客户端旧默认 180：抬到至少服务端 idle 默认，避免前端硬编码拖后腿
        if req <= 180:
            req = idle
        idle = req
    idle = max(60, min(idle, 3600))
    hard = max(idle, min(hard, 7200))
    return idle, hard


async def stream_chat(
    prompt: str,
    project_path: str,
    request_disconnected,
    timeout: int | None = None,
    model: str = "flash",
    resume_session_id: str | None = None,
    idle_timeout: int | None = None,
    max_timeout: int | None = None,
    hub_session_id: str | None = None,
    tool_mode: str = "discuss",
):
    """Yield SSE event dicts from a continuous ClaudeSDKClient session."""
    from .claude_session import session_manager
    from .. import config as _cfg

    idle_s, max_s = resolve_chat_timeouts(
        timeout,
        idle_default=idle_timeout,
        max_default=max_timeout,
    )
    sid = (hub_session_id or "").strip() or "anonymous"
    mode = _cfg.resolve_tool_mode(tool_mode, user_text=prompt)
    async for event in session_manager.stream_turn(
        prompt,
        project_path,
        sid,
        model=resolve_model(model),
        resume_session_id=resume_session_id,
        request_disconnected=request_disconnected,
        idle_timeout=idle_s,
        max_timeout=max_s,
        tool_mode=mode,
    ):
        yield event

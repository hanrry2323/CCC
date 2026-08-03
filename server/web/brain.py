"""server/web/brain.py — 大脑 Agent 对话模块（T29）。

`/conversation` 不再裸转发 6102，改为调用 2017 本机 Claude Code CLI
（走 `127.0.0.1:6100` Anthropic 出口），携带 CCC 大脑人格 + 历史上下文，
返回真实 Agent 输出（有心智/工具/知识库）。

调用方式::

    subprocess.run([claude, "-p", prompt, "--output-format", "text"],
                   env={...6100...}, timeout=CCC_BRAIN_TIMEOUT)

并发保护：模块级锁，同一时刻仅处理一个对话请求（单会话串行）；
失败/超时不落历史，返回明确错误码（503 未配置/忙 · 504 超时 · 502 失败）。

环境变量（零硬编码，2017 config.env 实际填写）::

    CCC_BRAIN_CLAUDE_BIN    Claude Code CLI 路径（默认 `claude`）
    CCC_BRAIN_MODEL         模型逻辑名（flash / Pro / code）
    CCC_BRAIN_BASE_URL      出口 base URL（如 http://127.0.0.1:6100）
    CCC_BRAIN_AUTH_TOKEN    出口 Bearer token
    CCC_BRAIN_TIMEOUT       调用超时秒（默认 60）
"""

from __future__ import annotations

import os
import subprocess
import threading
from typing import Any

# ── CCC 大脑人格（系统提示词，注入 prompt 头部） ──
BRAIN_SYSTEM_PROMPT = (
    "你是 CCC 的大脑 Agent，负责方案讨论、知识核查、任务拆解、多壳对话。"
    "你可以读取项目文档与知识库，按需调用工具。"
    "回答用中文，结论先行，条理清晰；禁止把问题抛回给用户做选择题。"
    "若信息不足，给出你最合理的判断与依据，而非反问。"
)

# 对话历史拼入 prompt 的最大轮数（user+assistant 算一轮）
_BRAIN_HISTORY_TURNS = 10

# 模块级锁：单会话串行，避免多壳同时打爆 Claude Code
_brain_lock = threading.Lock()


# ── 配置读取（运行时可刷新，测试可覆盖） ──
def _get_brain_claude_bin() -> str:
    """Claude Code CLI 可执行文件路径（默认 `claude`）。"""
    return os.environ.get("CCC_BRAIN_CLAUDE_BIN", "claude").strip() or "claude"


def _get_brain_model() -> str:
    """大脑模型逻辑名（如 flash / Pro / code）。"""
    return os.environ.get("CCC_BRAIN_MODEL", "").strip()


def _get_brain_base_url() -> str:
    """Claude Code 出口 base URL（如 http://127.0.0.1:6100）。"""
    return os.environ.get("CCC_BRAIN_BASE_URL", "").strip()


def _get_brain_auth_token() -> str:
    """Claude Code 出口 Bearer token。"""
    return os.environ.get("CCC_BRAIN_AUTH_TOKEN", "").strip()


def _get_brain_timeout() -> int:
    """大脑调用超时（秒，默认 60）。"""
    try:
        return int(os.environ.get("CCC_BRAIN_TIMEOUT", "60"))
    except ValueError:
        return 60


def _is_brain_configured() -> bool:
    """大脑代理配置是否齐全。

    `CCC_BRAIN_CLAUDE_BIN` 默认 `claude` 可用，故只校验 model / base_url / token。
    """
    return bool(_get_brain_model() and _get_brain_base_url() and _get_brain_auth_token())


def _build_prompt(message: str, history: list[dict[str, Any]]) -> str:
    """组装单次 Claude Code 调用 prompt：系统人格 + 最近 N 轮历史 + 当前消息。"""
    parts: list[str] = [BRAIN_SYSTEM_PROMPT, ""]
    recent = history[-(2 * _BRAIN_HISTORY_TURNS):] if history else []
    if recent:
        parts.append("【历史对话】")
        for entry in recent:
            role = entry.get("role", "")
            content = entry.get("message", "")
            if role in ("user", "assistant") and content:
                parts.append(f"{role}: {content}")
        parts.append("")
    parts.append("【当前问题】")
    parts.append(message)
    return "\n".join(parts)


def _run_claude(prompt: str, timeout: int) -> tuple[bool, str, str | None]:
    """调用 Claude Code CLI。

    返回 ``(success, stdout_or_error, error_kind)``：

    - 成功 → ``(True, stdout_text, None)``
    - 超时 → ``(False, "brain timeout", "timeout")``
    - 其他失败 → ``(False, "brain failed: <detail>", "failed")``

    env 在当前进程环境基础上覆盖三个 Anthropic 出口变量，指向 6100；
    Claude Code 全局配置（``~/.claude/settings.json``）保持不动。
    """
    bin_path = _get_brain_claude_bin()
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = _get_brain_base_url()
    env["ANTHROPIC_AUTH_TOKEN"] = _get_brain_auth_token()
    env["ANTHROPIC_MODEL"] = _get_brain_model()
    try:
        proc = subprocess.run(
            [bin_path, "-p", prompt, "--output-format", "text"],
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return (False, "brain timeout", "timeout")
    except (OSError, FileNotFoundError) as exc:
        return (False, f"brain failed: {exc}", "failed")

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()[:200] or f"exit {proc.returncode}"
        return (False, f"brain failed: {detail}", "failed")
    reply = (proc.stdout or "").strip()
    if not reply:
        return (False, "brain returned empty content", "failed")
    return (True, reply, None)


def call_brain(message: str, history: list[dict[str, Any]]) -> tuple[bool, str, int]:
    """大脑 Agent 对话入口（供 ``/conversation`` 调用）。

    返回 ``(success, reply_or_error, status_code)``：

    - 未配置 → ``(False, "brain not configured ...", 503)``
    - 忙（另一会话进行中） → ``(False, "brain busy, try later", 503)``
    - 超时 → ``(False, "brain timeout", 504)``
    - 失败 → ``(False, error_msg, 502)``
    - 成功 → ``(True, reply, 200)``
    """
    if not _is_brain_configured():
        return (
            False,
            "brain not configured (CCC_BRAIN_MODEL / CCC_BRAIN_BASE_URL / CCC_BRAIN_AUTH_TOKEN)",
            503,
        )
    prompt = _build_prompt(message, history)
    # 单会话串行：非阻塞获取锁，忙则立即拒绝（不排队等待，避免长阻塞）
    if not _brain_lock.acquire(blocking=False):
        return (False, "brain busy, try later", 503)
    try:
        ok, out, kind = _run_claude(prompt, _get_brain_timeout())
    finally:
        _brain_lock.release()
    if ok:
        return (True, out, 200)
    if kind == "timeout":
        return (False, out, 504)
    return (False, out, 502)

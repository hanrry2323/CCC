"""_product_session.py — Product Sessionful Contract Loop

替换一次性 `claude -p`：同一 ClaudeSDKClient 会话内
generate → parse/lint → 反馈错误 → 再生成，直到过线或微循环耗尽。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger("ccc.product.session")

MAX_MICRO_LOOPS = int(os.environ.get("CCC_PRODUCT_MICRO_LOOPS", "5") or "5")
MAX_MICRO_LOOPS = max(1, min(MAX_MICRO_LOOPS, 12))


def _extract_text(message: Any) -> str:
    parts: list[str] = []
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
    result = getattr(message, "result", None)
    if result and not parts:
        parts.append(str(result))
    return "".join(parts)


def parse_work_artifacts(output: str) -> tuple[str, list]:
    """Parse ---PLAN--- / ---PHASES--- blocks."""
    plan_match = re.search(
        r"---PLAN---\s*\n?(.*?)\n?---END_PLAN---", output or "", re.DOTALL
    )
    if not plan_match:
        raise RuntimeError("---PLAN--- section not found")
    phases_match = re.search(
        r"---PHASES---\s*\n?(.*?)\n?---END_PHASES---", output or "", re.DOTALL
    )
    if not phases_match:
        raise RuntimeError("---PHASES--- section not found")
    plan_content = plan_match.group(1).strip()
    phases: list = []
    for line in phases_match.group(1).strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # strip markdown fences if model wraps JSONL
        if line.startswith("```"):
            continue
        phases.append(json.loads(line))
    return plan_content, phases


def format_work_artifacts(plan: str, phases: list) -> str:
    lines = [json.dumps(p, ensure_ascii=False) for p in phases]
    return (
        f"---PLAN---\n{plan.strip()}\n---END_PLAN---\n"
        f"---PHASES---\n" + "\n".join(lines) + "\n---END_PHASES---\n"
    )


async def run_contract_loop(
    *,
    prompt: str,
    workspace: Path,
    task_id: str,
    mode: str = "work",
    model: str = "flash",
    max_loops: int | None = None,
    gate_fn: Callable[[str], tuple[str, Any]] | None = None,
    validate_fn: Callable[[str], None] | None = None,
) -> dict:
    """Run sessionful product loop.

    gate_fn(output) -> (canonical_output, payload) on success; raises on lint fail.
    validate_fn(output) raises on parse fail (before gate).

    Returns dict: ok, output, loops, claude_session_id, error
    """
    from _claude_cli import resolve_claude_cli
    from _cost_telemetry import estimate_tokens, record_call

    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
        )
    except ImportError as exc:
        return {
            "ok": False,
            "error": f"claude-agent-sdk missing: {exc}",
            "output": "",
            "loops": 0,
        }

    loops = max_loops if max_loops is not None else MAX_MICRO_LOOPS
    claude_bin = resolve_claude_cli(require=True)
    # Phase3：与 Engine 一致，勿全量继承个人 ~/.claude
    try:
        from _executor import _claude_env

        sdk_env = _claude_env()
    except Exception:
        sdk_env = {**os.environ}
    sdk_env["CLAUDE_PROJECT_DIR"] = str(workspace)
    options = ClaudeAgentOptions(
        cwd=str(workspace),
        model=model,
        allowed_tools=["Read", "Glob", "Grep", "LS"],
        permission_mode="bypassPermissions",
        cli_path=claude_bin,
        env=sdk_env,
    )

    repair_hint = (
        "\n\n硬约束：只输出契约块，不要包在 markdown code fence 里；"
        "phases 每行一个纯 JSON；plan 必须含独立二级标题 ## 验收。"
        if mode == "work"
        else "\n\n硬约束：只输出 ---EPIC_BRIEF--- / ---CHILDREN--- 契约块；"
        "CHILDREN 必须是可 json.loads 的 JSON 数组。"
    )

    user_msg = prompt + repair_hint
    session_id = ""
    last_error = ""
    accumulated = ""

    async with ClaudeSDKClient(options=options) as client:
        for i in range(loops):
            t0 = time.monotonic()
            await client.query(user_msg)
            texts: list[str] = []
            usage_in = 0
            usage_out = 0
            ok_turn = True
            async for message in client.receive_response():
                sid = getattr(message, "session_id", None)
                if isinstance(sid, str) and sid.strip():
                    session_id = sid.strip()
                if isinstance(message, AssistantMessage):
                    for block in message.content or []:
                        if isinstance(block, TextBlock) and block.text:
                            texts.append(block.text)
                    usage = getattr(message, "usage", None) or {}
                    usage_in = int(usage.get("input_tokens") or usage_in or 0)
                    usage_out = int(usage.get("output_tokens") or usage_out or 0)
                if isinstance(message, ResultMessage):
                    if message.session_id:
                        session_id = message.session_id
                    if message.is_error:
                        ok_turn = False
                        last_error = "; ".join(
                            str(e) for e in (message.errors or [])
                        ) or (message.result or "error")
                    elif message.result and not texts:
                        texts.append(str(message.result))
                    usage = message.usage or {}
                    if not usage_in:
                        usage_in = int(usage.get("input_tokens") or 0)
                    if not usage_out:
                        usage_out = int(usage.get("output_tokens") or 0)

            turn_text = "".join(texts).strip()
            accumulated = turn_text or accumulated
            latency_ms = int((time.monotonic() - t0) * 1000)
            if not usage_in and not usage_out:
                usage_in = estimate_tokens(user_msg)
                usage_out = estimate_tokens(turn_text)
            record_call(
                role="planner",
                provider_or_model=model,
                prompt_tokens=usage_in,
                completion_tokens=usage_out,
                latency_ms=latency_ms,
                ok=ok_turn and bool(turn_text),
                task_id=task_id,
                phase_id=f"product-micro-{i + 1}",
            )

            if not turn_text:
                last_error = last_error or "empty model output"
                user_msg = (
                    f"上一轮没有产出有效文本。错误：{last_error}\n"
                    f"请重新完整输出契约块。"
                )
                _log.warning(
                    "[product-session] %s loop %d/%d empty", task_id, i + 1, loops
                )
                continue

            try:
                if validate_fn is not None:
                    validate_fn(turn_text)
                if gate_fn is not None:
                    canonical, _payload = gate_fn(turn_text)
                else:
                    canonical = turn_text
                _log.info(
                    "[product-session] %s ✓ contract passed loop=%d sid=%s",
                    task_id,
                    i + 1,
                    session_id[:8] if session_id else "?",
                )
                return {
                    "ok": True,
                    "output": canonical,
                    "loops": i + 1,
                    "claude_session_id": session_id,
                    "error": "",
                }
            except Exception as exc:
                last_error = str(exc)
                _log.warning(
                    "[product-session] %s loop %d/%d lint/parse: %s",
                    task_id,
                    i + 1,
                    loops,
                    last_error[:200],
                )
                user_msg = (
                    f"契约校验失败，请在同一任务上修正后重新完整输出契约块。\n"
                    f"错误：{last_error}\n"
                    f"不要解释过程；只输出修正后的契约。"
                )

    return {
        "ok": False,
        "output": accumulated,
        "loops": loops,
        "claude_session_id": session_id,
        "error": f"contract micro-loops exhausted ({loops}): {last_error}",
    }


def run_contract_loop_sync(**kwargs) -> dict:
    return asyncio.run(run_contract_loop(**kwargs))

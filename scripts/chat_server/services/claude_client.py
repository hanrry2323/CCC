import asyncio
import json
import logging
import time
from pathlib import Path

from .. import config

_log = logging.getLogger("ccc-chat")


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
):
    """Generator that yields SSE event dicts from Claude subprocess.

    超时策略：空闲超时（有输出重置）+ 硬墙钟上限；等待读时发 ping 保活。
    """
    proc = None
    idle_s, max_s = resolve_chat_timeouts(
        timeout,
        idle_default=idle_timeout,
        max_default=max_timeout,
    )
    try:
        claude_bin = config.require_claude_bin()
        allowed = ",".join(sorted(config.CLAUDE_TOOL_ALLOWLIST))
        cli_model = resolve_model(model)
        cmd = [
            claude_bin,
            "-p",
            "--print",
            "--verbose",
            "--output-format",
            "stream-json",
            "--model",
            cli_model,
            "--allowedTools",
            allowed,
        ]
        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**config.CLAUDE_ENV, "CLAUDE_PROJECT_DIR": project_path},
        )
        assert proc.stdin is not None
        proc.stdin.write(prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()

        async def _read_stderr():
            if proc.stderr:
                async for line in proc.stderr:
                    _log.warning(
                        "claude stderr: %s", line.decode(errors="replace").rstrip()
                    )

        stderr_task = asyncio.create_task(_read_stderr())

        started = time.monotonic()
        last_activity = started
        last_ping = started
        buffer = b""
        saw_assistant_text = False
        timed_out = False

        while True:
            if request_disconnected():
                proc.kill()
                break

            now = time.monotonic()
            if now - started >= max_s:
                proc.kill()
                timed_out = True
                yield {
                    "type": "error",
                    "content": f"响应超时（整轮上限 {max_s}s），请重试或缩短任务",
                }
                break
            idle_left = idle_s - (now - last_activity)
            if idle_left <= 0:
                proc.kill()
                timed_out = True
                yield {
                    "type": "error",
                    "content": (
                        f"响应超时（已 {idle_s}s 无新输出；"
                        f"整轮上限 {max_s}s），请重试"
                    ),
                }
                break

            try:
                chunk = await asyncio.wait_for(
                    proc.stdout.read(4096),
                    timeout=min(max(idle_left, 0.1), 5.0),
                )
            except asyncio.TimeoutError:
                if proc.returncode is not None:
                    break
                # SSE 心跳：避免反向代理 / 浏览器掐掉长时间静默连接
                now = time.monotonic()
                if now - last_ping >= 15:
                    yield {"type": "ping", "ts": int(now)}
                    last_ping = now
                continue

            if not chunk:
                break

            last_activity = time.monotonic()
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line_str = line.decode(errors="replace").strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str)
                except json.JSONDecodeError:
                    continue
                evt_type = event.get("type")
                if evt_type == "assistant":
                    msg = event.get("message", {})
                    for block in msg.get("content", []):
                        btype = block.get("type")
                        if btype == "text":
                            text = block.get("text", "")
                            if text:
                                saw_assistant_text = True
                                yield {"type": "delta", "content": text}
                        elif btype == "tool_use":
                            yield {
                                "type": "tool_use",
                                "name": block.get("name", "tool"),
                                "input": block.get("input", {}),
                            }
                elif evt_type == "user":
                    msg = event.get("message", {})
                    for block in msg.get("content", []):
                        if block.get("type") == "tool_result":
                            yield {
                                "type": "tool_result",
                                "content": block.get("content", ""),
                            }
                elif evt_type == "result":
                    yield {
                        "type": "cost",
                        "tokens": (
                            (event.get("usage", {}).get("input_tokens", 0) or 0)
                            + (event.get("usage", {}).get("output_tokens", 0) or 0)
                        ),
                        "usd": event.get("total_cost_usd", 0) or 0,
                    }
                    result_text = event.get("result", "")
                    if result_text and not saw_assistant_text:
                        yield {"type": "delta", "content": result_text}

        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

        stderr_task.cancel()
        try:
            await stderr_task
        except asyncio.CancelledError:
            pass

        if not timed_out:
            yield {"type": "done", "session_id": ""}

    except (GeneratorExit, asyncio.CancelledError):
        raise
    finally:
        if proc and proc.returncode is None:
            proc.kill()

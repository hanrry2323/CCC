import asyncio
import json
import logging
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


async def stream_chat(
    prompt: str,
    project_path: str,
    request_disconnected,
    timeout: int = 180,
    model: str = "flash",
    resume_session_id: str | None = None,
):
    """Generator that yields SSE event dicts from Claude subprocess."""
    proc = None
    try:
        # F-SEC-06: 显式要求 PATH 中的 claude
        claude_bin = config.require_claude_bin()
        # F-SEC-03: 工具 allowlist + cwd jail（仅 project_path）
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
        # 续聊 Claude Code 本地会话（与 CLI -r 对齐）
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
                    _log.warning("claude stderr: %s", line.decode(errors="replace").rstrip())

        stderr_task = asyncio.create_task(_read_stderr())

        deadline = asyncio.get_event_loop().time() + timeout
        buffer = b""

        while True:
            if request_disconnected():
                proc.kill()
                break
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                proc.kill()
                yield {"type": "error", "content": "响应超时（180s），请重试"}
                break
            try:
                chunk = await asyncio.wait_for(
                    proc.stdout.read(4096), timeout=min(remaining, 5.0)
                )
            except asyncio.TimeoutError:
                if proc.returncode is not None:
                    break
                continue
            if not chunk:
                break
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
                    if result_text:
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

        yield {"type": "done", "session_id": ""}

    except (GeneratorExit, asyncio.CancelledError):
        raise
    finally:
        if proc and proc.returncode is None:
            proc.kill()

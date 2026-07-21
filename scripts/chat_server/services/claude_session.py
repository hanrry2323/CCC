"""Hub continuous Claude sessions via Claude Agent SDK (ClaudeSDKClient).

Replaces per-turn `claude -p` spawn/kill. One live client per Hub session;
idle/LRU disconnect; cold resume via Claude session_id.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .. import config

_log = logging.getLogger("ccc-chat.session")

# Claude Code / loop-code 偶发合成 stub（空内容或 meta 续跑），对用户等于死回复
_NO_RESPONSE_STUB_RE = re.compile(
    r"^\s*no\s+response\s+requested\.?\s*$",
    re.I,
)
_STUB_RETRY_PROMPT = (
    "上一条用户请求仍然有效，请立刻给出对用户可见的完整中文答复。"
    "禁止回复 No response requested、空内容或只跑工具不说话。"
)
_STUB_CANON = "no response requested."


def _is_no_response_stub(text: str) -> bool:
    return bool(_NO_RESPONSE_STUB_RE.match((text or "").strip()))


def _could_be_stub_prefix(text: str) -> bool:
    """流式中尚未结束时：是否仍可能拼成 stub（避免把 N/o/... 提前推给 UI）。"""
    s = (text or "").strip().lower()
    if not s:
        return True
    if _is_no_response_stub(s):
        return True
    # 过长或明显不是 stub 前缀 → 放行
    if len(s) > len(_STUB_CANON) + 2:
        return False
    return _STUB_CANON.startswith(s) or s.startswith("no response")


def _descendant_loop_code_pids(root_pid: int | None = None) -> set[int]:
    """sidecar 进程树内 loop-code/cli PID（用于 disconnect 后硬清理僵尸）。"""
    root = int(root_pid or os.getpid())
    found: set[int] = set()
    try:
        # macOS/Linux: 广度优先扫子进程
        queue = [root]
        seen = {root}
        while queue:
            parent = queue.pop(0)
            try:
                out = subprocess.check_output(
                    ["pgrep", "-P", str(parent)],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                continue
            for part in out.split():
                if not part.isdigit():
                    continue
                child = int(part)
                if child in seen:
                    continue
                seen.add(child)
                queue.append(child)
                try:
                    cmd = subprocess.check_output(
                        ["ps", "-p", str(child), "-o", "command="],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    ).strip()
                except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                    continue
                if "loop-code/cli" in cmd or cmd.endswith("/loop-code/cli"):
                    found.add(child)
    except Exception:
        _log.debug("scan loop-code children failed", exc_info=True)
    return found


def _kill_pids(pids: set[int], *, reason: str) -> int:
    killed = 0
    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except ProcessLookupError:
            continue
        except OSError:
            _log.debug("kill pid=%s reason=%s failed", pid, reason, exc_info=True)
    if killed:
        _log.warning("killed %d loop-code pid(s) reason=%s pids=%s", killed, reason, sorted(pids))
    return killed


def _escalate_kill_pids(pids: set[int], *, reason: str) -> int:
    """SIGTERM 一次 + 短等待，未退则 SIGKILL。严格只针对 slot 已登记的 PID。"""
    killed = _kill_pids(pids, reason=reason)
    survivors: set[int] = set()
    for pid in sorted(pids):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except OSError:
            continue
        survivors.add(pid)
    if not survivors:
        return killed
    import time as _time

    _time.sleep(min(0.3, 0.2))
    for pid in sorted(survivors):
        try:
            os.kill(pid, signal.SIGKILL)
            killed += 1
        except ProcessLookupError:
            continue
        except OSError:
            _log.debug("sigkill pid=%s reason=%s failed", pid, reason, exc_info=True)
    if killed:
        _log.warning(
            "escalate killed %d loop-code pid(s) reason=%s pids=%s",
            killed, reason, sorted(pids),
        )
    return killed


def _pids_alive(pids: set[int]) -> bool:
    """任一 PID 仍存活则 True；空集合视为未知（不判死）。"""
    if not pids:
        return True
    for pid in pids:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            continue
        except PermissionError:
            return True
        except OSError:
            continue
    return False

try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        SystemMessage,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )
except ImportError as _exc:  # pragma: no cover - surfaced at turn time
    AssistantMessage = None  # type: ignore[misc, assignment]
    ClaudeAgentOptions = None  # type: ignore[misc, assignment]
    ClaudeSDKClient = None  # type: ignore[misc, assignment]
    ResultMessage = None  # type: ignore[misc, assignment]
    SystemMessage = None  # type: ignore[misc, assignment]
    TextBlock = None  # type: ignore[misc, assignment]
    ToolResultBlock = None  # type: ignore[misc, assignment]
    ToolUseBlock = None  # type: ignore[misc, assignment]
    UserMessage = None  # type: ignore[misc, assignment]
    _SDK_IMPORT_ERROR = _exc
else:
    _SDK_IMPORT_ERROR = None


def _slot_key(
    project_path: str, hub_session_id: str, tool_mode: str = "discuss"
) -> str:
    """Live slot 键：同项目同 Desktop thread 共用一槽。

    tool_mode 不再进 key（discuss↔engineer 改工具集时走同槽 reconnect + resume），
    否则同会话中途切模式会开新脑、丢掉连续对话。
    """
    _ = tool_mode  # 保留参数兼容旧调用方
    return f"{project_path}::{hub_session_id}"


@dataclass
class _LiveSlot:
    key: str
    project_path: str
    hub_session_id: str
    model: str
    client: Any
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    claude_session_id: str | None = None
    last_used: float = field(default_factory=time.monotonic)
    connected: bool = False
    tool_mode: str = "discuss"
    cli_pids: set[int] = field(default_factory=set)
    allowed_tools: frozenset[str] = field(default_factory=frozenset)
    tools_bound: bool = False


class ClaudeSessionManager:
    """Process-wide manager for Hub ClaudeSDKClient slots."""

    def __init__(
        self,
        *,
        idle_ttl: int | None = None,
        max_live: int | None = None,
    ) -> None:
        self._idle_ttl = int(
            idle_ttl if idle_ttl is not None else config.CHAT_SESSION_IDLE_TTL
        )
        self._max_live = int(
            max_live if max_live is not None else config.CHAT_SESSION_MAX_LIVE
        )
        self._slots: dict[str, _LiveSlot] = {}
        self._global_lock = asyncio.Lock()
        self._reaper_task: asyncio.Task | None = None
        # 压缩后待注入的摘要：key → summary text；下次 stream_turn 取出并 prepend
        self._pending_summaries: dict[str, str] = {}

    def _ensure_sdk(self) -> None:
        if _SDK_IMPORT_ERROR is not None or ClaudeSDKClient is None:
            raise RuntimeError(
                "claude-agent-sdk not installed; use .venv-hub "
                "(pip install -r requirements-hub.txt)"
            ) from _SDK_IMPORT_ERROR

    def _ensure_reaper(self) -> None:
        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = asyncio.create_task(
                self._reaper_loop(), name="ccc-chat-session-reaper"
            )

    async def _reaper_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(30)
                await self.reap_idle()
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("session reaper error")

    async def reap_idle(self) -> int:
        """Disconnect slots idle longer than TTL. Returns count closed."""
        now = time.monotonic()
        to_close: list[str] = []
        async with self._global_lock:
            for key, slot in self._slots.items():
                if now - slot.last_used >= self._idle_ttl:
                    to_close.append(key)
        closed = 0
        for key in to_close:
            if await self._drop_slot(key, reason="idle"):
                closed += 1
        return closed

    async def _evict_lru_if_needed(self, keep_key: str) -> None:
        async with self._global_lock:
            if len(self._slots) < self._max_live:
                return
            candidates = [
                (s.last_used, k)
                for k, s in self._slots.items()
                if k != keep_key
            ]
            if not candidates:
                return
            candidates.sort()
            victim = candidates[0][1]
        await self._drop_slot(victim, reason="lru")

    async def _acquire_slot_lock(
        self, slot: _LiveSlot, *, timeout: float, reason: str
    ) -> bool:
        """带超时拿 slot 锁。失败返回 False（调用方应失败快返回 / force-drop）。"""
        try:
            await asyncio.wait_for(slot.lock.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            _log.warning(
                "slot lock timeout key=%s wait=%.1fs reason=%s",
                slot.key,
                timeout,
                reason,
            )
            return False

    async def _drop_slot(self, key: str, *, reason: str) -> bool:
        async with self._global_lock:
            slot = self._slots.pop(key, None)
        if slot is None:
            return False
        got = await self._acquire_slot_lock(
            slot, timeout=float(config.CHAT_LOCK_WAIT), reason=f"drop:{reason}"
        )
        try:
            if got:
                await self._disconnect_slot(slot)
            else:
                # 锁被占死：尽力 disconnect，避免永久假死
                _log.warning(
                    "force disconnect without lock key=%s reason=%s",
                    key,
                    reason,
                )
                await self._disconnect_slot(slot)
        finally:
            if got and slot.lock.locked():
                slot.lock.release()
        _log.info(
            "dropped Claude session slot key=%s reason=%s claude_sid=%s",
            key,
            reason,
            slot.claude_session_id,
        )
        return True

    async def _bounded_drain(self, slot: _LiveSlot) -> None:
        """超时后有界排空 receive_response；失败则 disconnect，禁止无限占锁。"""
        if not slot.connected or slot.client is None:
            return
        drain_s = float(config.CHAT_DRAIN_TIMEOUT)

        async def _drain() -> None:
            async for _ in slot.client.receive_response():
                pass

        try:
            await asyncio.wait_for(_drain(), timeout=drain_s)
        except asyncio.TimeoutError:
            _log.warning(
                "drain timeout key=%s after %.1fs → disconnect",
                slot.key,
                drain_s,
            )
            await self._disconnect_slot(slot)
        except Exception:
            _log.debug("drain failed key=%s", slot.key, exc_info=True)
            await self._disconnect_slot(slot)

    async def compact_session(
        self,
        *,
        project_path: str,
        hub_session_id: str,
        summary: str | None,
        tool_mode: str = "discuss",
        model: str = "flash",
    ) -> str:
        """压缩 agent session：drop slot + 存摘要待下次注入。

        若 summary 为空，本可先跑一轮总结；为避免阻塞 HTTP 请求，
        这里直接用占位摘要（调用方应自行生成摘要传入）。
        返回最终使用的 summary 文本。
        """
        mode = config.resolve_tool_mode(tool_mode)
        key = _slot_key(project_path, hub_session_id, mode)
        final_summary = (summary or "").strip()
        if not final_summary:
            final_summary = "（对话已压缩；本机磁盘保留完整历史）"
        await self._drop_slot(key, reason="compact")
        self._pending_summaries[key] = final_summary
        _log.info(
            "compact session key=%s sid=%s summary_len=%d",
            key,
            hub_session_id,
            len(final_summary),
        )
        return final_summary

    async def _disconnect_slot(self, slot: _LiveSlot) -> None:
        try:
            if slot.connected and slot.client is not None:
                try:
                    await asyncio.wait_for(
                        slot.client.disconnect(),
                        timeout=float(config.CHAT_DRAIN_TIMEOUT),
                    )
                except asyncio.TimeoutError:
                    _log.warning(
                        "disconnect timeout key=%s → escalate to SIGKILL",
                        slot.key,
                    )
                if slot.cli_pids:
                    _escalate_kill_pids(
                        set(slot.cli_pids),
                        reason=f"disconnect:{slot.key}",
                    )
                    slot.cli_pids.clear()
        except Exception:
            _log.warning(
                "disconnect failed for %s", slot.hub_session_id, exc_info=True
            )
        finally:
            slot.connected = False
            slot.client = None
            slot.tools_bound = False

    async def _forget_slot(self, slot: _LiveSlot, *, reason: str) -> None:
        """调用方已持有 slot.lock：断开并移出 registry，供挂死轮次回收。"""
        await self._disconnect_slot(slot)
        async with self._global_lock:
            cur = self._slots.get(slot.key)
            if cur is slot:
                self._slots.pop(slot.key, None)
        _log.info(
            "forgot Claude session slot key=%s hub_sid=%s reason=%s",
            slot.key,
            slot.hub_session_id,
            reason,
        )

    def _build_options(
        self,
        *,
        project_path: str,
        model: str,
        resume_session_id: str | None,
        tool_mode: str = "discuss",
        user_text: str = "",
        prompt_mode: str | None = None,
        allowed_tools: frozenset[str] | None = None,
    ) -> Any:
        self._ensure_sdk()
        claude_bin = config.require_claude_bin()
        mode = config.resolve_tool_mode(tool_mode)
        # 注意：空 frozenset() 表示「零工具」，不能用 `or`（空集合在 Python 为 falsy）
        if allowed_tools is None:
            allowed_set = config.tools_for_mode(
                mode, user_text=user_text, prompt_mode=prompt_mode
            )
        else:
            allowed_set = allowed_tools
        allowed = sorted(allowed_set)
        kwargs: dict[str, Any] = {
            "cwd": project_path,
            "model": model,
            "allowed_tools": allowed,
            # Hub 无 TTY：勿用 acceptEdits（Bash 等仍可能卡住等人点许可）
            "permission_mode": "bypassPermissions",
            "cli_path": claude_bin,
            "env": {
                **config.CLAUDE_ENV,
                "CLAUDE_PROJECT_DIR": project_path,
            },
        }
        # SDK：allowed_tools 为空时不加 --allowedTools（= 默认全开）。
        # 零工具轮次必须显式 disallowed_tools，否则短问仍会 WebFetch 挂死。
        if not allowed:
            deny = sorted(
                set(config.CLAUDE_TOOL_ALLOWLIST_ENGINEER)
                | set(config.CLAUDE_TOOL_ALLOWLIST_DISCUSS)
                | {
                    "Agent",
                    "Skill",
                    "NotebookEdit",
                    "WebFetch",
                    "WebSearch",
                    "Bash",
                }
            )
            kwargs["disallowed_tools"] = deny
        if resume_session_id:
            kwargs["resume"] = resume_session_id
        return ClaudeAgentOptions(**kwargs)

    async def _get_or_create_slot(
        self,
        *,
        project_path: str,
        hub_session_id: str,
        model: str,
        resume_session_id: str | None,
        tool_mode: str = "discuss",
    ) -> _LiveSlot:
        self._ensure_sdk()
        self._ensure_reaper()
        mode = config.resolve_tool_mode(tool_mode)
        key = _slot_key(project_path, hub_session_id, mode)

        async with self._global_lock:
            slot = self._slots.get(key)
            if slot is not None:
                # Model change → recreate on next connect
                if slot.model != model and not slot.connected:
                    slot.model = model
                return slot

        await self._evict_lru_if_needed(key)

        slot = _LiveSlot(
            key=key,
            project_path=project_path,
            hub_session_id=hub_session_id,
            model=model,
            client=None,
            claude_session_id=resume_session_id,
            tool_mode=mode,
        )
        async with self._global_lock:
            existing = self._slots.get(key)
            if existing is not None:
                # Race: another coroutine created first
                return existing
            self._slots[key] = slot
        return slot

    async def _ensure_connected(
        self,
        slot: _LiveSlot,
        *,
        resume_session_id: str | None,
        model: str,
        user_text: str = "",
        prompt_mode: str | None = None,
        allowed_tools: frozenset[str] | None = None,
    ) -> None:
        mode = getattr(slot, "tool_mode", "discuss")
        if allowed_tools is None:
            desired = config.tools_for_mode(
                mode, user_text=user_text, prompt_mode=prompt_mode
            )
        else:
            desired = allowed_tools
        # 工具集变更（如短问推迟 Web*）→ 必须重建连接，SDK 无法热替换 allowlist
        # tools_bound 区分「尚未绑定」与「已绑定为零工具」
        if (
            slot.connected
            and slot.client is not None
            and slot.tools_bound
            and set(slot.allowed_tools) != set(desired)
        ):
            _log.info(
                "tool allowlist changed key=%s old=%s new=%s → reconnect",
                slot.key,
                sorted(slot.allowed_tools),
                sorted(desired),
            )
            await self._disconnect_slot(slot)

        if slot.connected and slot.client is not None:
            # 半残 slot：cli PID 全死但仍标 connected → 强制重连，防下一轮 first_event 假死
            if slot.cli_pids and not _pids_alive(slot.cli_pids):
                _log.warning(
                    "stale slot cli dead key=%s hub_sid=%s → disconnect+reconnect",
                    slot.key,
                    slot.hub_session_id,
                )
                await self._disconnect_slot(slot)
            else:
                return
        # Prefer stored / requested resume id
        resume = resume_session_id or slot.claude_session_id
        if slot.model != model:
            slot.model = model
        options = self._build_options(
            project_path=slot.project_path,
            model=slot.model,
            resume_session_id=resume,
            tool_mode=mode,
            user_text=user_text,
            prompt_mode=prompt_mode,
            allowed_tools=desired,
        )
        slot.client = ClaudeSDKClient(options=options)
        connect_s = float(config.CHAT_CONNECT_TIMEOUT)
        before_pids = _descendant_loop_code_pids()
        try:
            await asyncio.wait_for(slot.client.connect(), timeout=connect_s)
        except asyncio.TimeoutError as exc:
            slot.connected = False
            slot.client = None
            # connect 超时也可能已拉起半残 cli
            orphan = _descendant_loop_code_pids() - before_pids
            if orphan:
                _kill_pids(orphan, reason=f"connect_timeout:{slot.key}")
            raise TimeoutError(
                f"Claude 连接超时（{int(connect_s)}s）"
            ) from exc
        slot.connected = True
        slot.allowed_tools = frozenset(desired)
        slot.tools_bound = True
        slot.cli_pids = _descendant_loop_code_pids() - before_pids
        if resume:
            slot.claude_session_id = resume

    @staticmethod
    def _extract_session_id(message: Any) -> str | None:
        sid = getattr(message, "session_id", None)
        if isinstance(sid, str) and sid.strip():
            return sid.strip()
        if SystemMessage is not None and isinstance(message, SystemMessage):
            data = getattr(message, "data", None) or {}
            if isinstance(data, dict):
                raw = data.get("session_id")
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
        return None

    @staticmethod
    def _map_message(message: Any) -> list[dict[str, Any]]:
        """Map one SDK message to zero or more Hub SSE event dicts."""
        events: list[dict[str, Any]] = []
        if AssistantMessage is not None and isinstance(message, AssistantMessage):
            blocks = message.content or []
            # 若本条 AssistantMessage 同时含 ToolUseBlock，则 TextBlock 视为
            # 工具期间的阶段性短句 → 映射为 status（区别于主通道 delta）
            has_tool_use = any(
                ToolUseBlock is not None and isinstance(b, ToolUseBlock)
                for b in blocks
            )
            for block in blocks:
                if TextBlock is not None and isinstance(block, TextBlock):
                    text = block.text or ""
                    if not text:
                        continue
                    if has_tool_use:
                        events.append({"type": "status", "content": text})
                    else:
                        events.append({"type": "delta", "content": text})
                elif ToolUseBlock is not None and isinstance(block, ToolUseBlock):
                    events.append({
                        "type": "tool_use",
                        "name": block.name or "tool",
                        "input": block.input or {},
                    })
                elif ToolResultBlock is not None and isinstance(block, ToolResultBlock):
                    content = block.content
                    if not isinstance(content, str):
                        content = str(content) if content is not None else ""
                    events.append({"type": "tool_result", "content": content})
            return events

        if UserMessage is not None and isinstance(message, UserMessage):
            content = message.content
            if isinstance(content, list):
                for block in content:
                    if ToolResultBlock is not None and isinstance(
                        block, ToolResultBlock
                    ):
                        raw = block.content
                        if not isinstance(raw, str):
                            raw = str(raw) if raw is not None else ""
                        events.append({"type": "tool_result", "content": raw})
            return events

        if ResultMessage is not None and isinstance(message, ResultMessage):
            usage = message.usage or {}
            tokens = int(usage.get("input_tokens", 0) or 0) + int(
                usage.get("output_tokens", 0) or 0
            )
            events.append({
                "type": "cost",
                "tokens": tokens,
                "usd": message.total_cost_usd or 0,
            })
            if message.is_error:
                err = ""
                if message.errors:
                    err = "; ".join(str(e) for e in message.errors)
                elif message.result:
                    err = str(message.result)
                events.append({
                    "type": "error",
                    "content": err or "Claude session error",
                })
            elif message.result:
                # Fallback text if no assistant deltas were streamed
                events.append({
                    "type": "_result_text",
                    "content": str(message.result),
                })
            return events

        return events

    async def stream_turn(
        self,
        prompt: str,
        project_path: str,
        hub_session_id: str,
        *,
        model: str = "flash",
        resume_session_id: str | None = None,
        request_disconnected=None,
        idle_timeout: int | None = None,
        max_timeout: int | None = None,
        tool_mode: str = "discuss",
        prompt_mode: str | None = None,
        user_text_for_tools: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run one user turn on a continuous ClaudeSDKClient session."""
        self._ensure_sdk()
        # model / timeouts already resolved by stream_chat caller
        from _claude_cli import resolve_anthropic_model

        cli_model = resolve_anthropic_model(model)
        idle_s = int(idle_timeout if idle_timeout is not None else config.CHAT_IDLE_TIMEOUT)
        max_s = int(max_timeout if max_timeout is not None else config.CHAT_MAX_TIMEOUT)
        idle_s = max(60, min(idle_s, 3600))
        max_s = max(idle_s, min(max_s, 7200))
        mode = config.resolve_tool_mode(tool_mode)
        # 必须用用户原文算工具集；wrap 后的人格前缀会很长，会误开 Web*
        tool_src = (
            user_text_for_tools if user_text_for_tools is not None else prompt
        )
        turn_tools = config.tools_for_mode(
            mode, user_text=tool_src, prompt_mode=prompt_mode
        )
        _log.info(
            "stream_turn tools hub_sid=%s mode=%s prompt_mode=%s n_tools=%d tools=%s",
            hub_session_id,
            mode,
            prompt_mode,
            len(turn_tools),
            sorted(turn_tools),
        )

        slot = await self._get_or_create_slot(
            project_path=project_path,
            hub_session_id=hub_session_id,
            model=cli_model,
            resume_session_id=resume_session_id,
            tool_mode=mode,
        )

        lock_wait = float(config.CHAT_LOCK_WAIT)
        got_lock = await self._acquire_slot_lock(
            slot, timeout=lock_wait, reason="stream_turn"
        )
        if not got_lock:
            # 同项目被挂死 turn 占锁：force-drop 后让客户端重试
            await self._drop_slot(slot.key, reason="lock_timeout")
            yield {
                "type": "error",
                "content": (
                    f"本机 Agent 会话忙或挂死（等锁 {int(lock_wait)}s），"
                    "已强制释放，请重试"
                ),
                "code": "lock_timeout",
            }
            yield {
                "type": "done",
                "session_id": hub_session_id,
                "claude_session_id": "",
                "partial": True,
            }
            return

        try:
            slot.last_used = time.monotonic()
            # 立刻心跳：connect 可能要数秒，避免前端一直空白
            yield {"type": "ping", "ts": int(time.time())}

            try:
                await self._ensure_connected(
                    slot,
                    resume_session_id=resume_session_id,
                    model=cli_model,
                    user_text=tool_src,
                    prompt_mode=prompt_mode,
                    allowed_tools=turn_tools,
                )
            except Exception as exc:
                # 一次失败：断槽再连，覆盖「假 connected」残留
                _log.warning(
                    "ensure_connected failed hub_sid=%s key=%s → retry once: %s",
                    hub_session_id,
                    slot.key,
                    exc,
                )
                await self._disconnect_slot(slot)
                try:
                    await self._ensure_connected(
                        slot,
                        resume_session_id=resume_session_id,
                        model=cli_model,
                        user_text=tool_src,
                        prompt_mode=prompt_mode,
                        allowed_tools=turn_tools,
                    )
                except Exception as exc2:
                    slot.connected = False
                    yield {
                        "type": "error",
                        "content": f"Claude 会话连接失败: {exc2}",
                        "code": "hang" if isinstance(exc2, TimeoutError) else "connect_failed",
                    }
                    yield {
                        "type": "done",
                        "session_id": hub_session_id,
                        "claude_session_id": slot.claude_session_id or "",
                        "partial": True,
                    }
                    return

            started = time.monotonic()
            # 进展时钟：仅 delta/tool/status/cost/error 推进；心跳 ping 不算进展
            last_progress = started
            last_ping = started
            awaiting_first_event = True
            pending_tool: str | None = None
            first_event_s = int(config.CHAT_FIRST_EVENT_TIMEOUT)
            tool_stall_s = int(config.CHAT_TOOL_STALL_TIMEOUT)
            saw_assistant_text = False
            timed_out = False
            stall_reason = ""
            turn_error = False
            client_gone = False
            reader_task: asyncio.Task | None = None
            assistant_text_buf = ""
            stub_retry_used = False
            held_delta = ""  # 疑似 stub 前缀时暂存，确认非 stub 再冲刷

            # 关键：不可对 receive_response().__anext__ 使用 wait_for——
            # 超时会 cancel 底层迭代，导致整轮无 delta、只剩空 done。
            msg_queue: asyncio.Queue = asyncio.Queue()

            async def _reader() -> None:
                try:
                    async for message in slot.client.receive_response():
                        await msg_queue.put(("msg", message))
                except Exception as exc:
                    await msg_queue.put(("err", exc))
                finally:
                    await msg_queue.put(("end", None))

            def _stall_limit() -> int:
                if awaiting_first_event:
                    return first_event_s
                if pending_tool:
                    return tool_stall_s
                return idle_s

            try:
                effective_prompt = prompt
                # 注入压缩摘要：drop slot 后首条 query 前置摘要
                if slot.key in self._pending_summaries:
                    summary = self._pending_summaries.pop(slot.key)
                    effective_prompt = (
                        f"以下是之前对话的压缩摘要，请基于此继续：\n\n{summary}\n\n"
                        f"---\n\n用户新消息：{prompt}"
                    )

                # 最多两轮：首轮若只有 Claude Code stub「No response requested.」则静默续问一次
                for attempt in range(2):
                    if attempt == 1:
                        if stub_retry_used:
                            break
                        if client_gone or timed_out or turn_error:
                            break
                        if not _is_no_response_stub(assistant_text_buf):
                            break
                        stub_retry_used = True
                        _log.warning(
                            "suppress no-response stub; retry once hub_sid=%s",
                            hub_session_id,
                        )
                        assistant_text_buf = ""
                        held_delta = ""
                        saw_assistant_text = False
                        awaiting_first_event = True
                        pending_tool = None
                        last_progress = time.monotonic()
                        effective_prompt = _STUB_RETRY_PROMPT

                    await slot.client.query(effective_prompt)
                    last_progress = time.monotonic()
                    reader_task = asyncio.create_task(
                        _reader(), name=f"ccc-chat-reader-{hub_session_id[:12]}"
                    )
                    attempt_ended = False

                    while True:
                        if request_disconnected and request_disconnected():
                            client_gone = True
                            try:
                                await slot.client.interrupt()
                            except Exception:
                                _log.debug(
                                    "interrupt on disconnect failed", exc_info=True
                                )
                            break

                        now = time.monotonic()
                        if now - started >= max_s:
                            timed_out = True
                            stall_reason = f"整轮上限 {max_s}s"
                            try:
                                await slot.client.interrupt()
                            except Exception:
                                pass
                            yield {
                                "type": "error",
                                "code": "max_timeout",
                                "content": f"响应超时（{stall_reason}），请重试或缩短任务",
                            }
                            break

                        limit = _stall_limit()
                        idle_left = limit - (now - last_progress)
                        if idle_left <= 0:
                            timed_out = True
                            try:
                                await slot.client.interrupt()
                            except Exception:
                                pass
                            if awaiting_first_event:
                                stall_reason = (
                                    f"首事件超时 {first_event_s}s（仅心跳无输出）"
                                )
                                code = "first_event_timeout"
                            elif pending_tool:
                                stall_reason = (
                                    f"工具 {pending_tool} 超过 {tool_stall_s}s 无结果"
                                )
                                code = "tool_stall"
                            else:
                                stall_reason = f"已 {idle_s}s 无新输出"
                                code = "idle_timeout"
                            yield {
                                "type": "error",
                                "code": code,
                                "content": (
                                    f"Agent 无进展：{stall_reason}。"
                                    "已中断并回收会话，请重试。"
                                ),
                            }
                            break

                        try:
                            kind, payload = await asyncio.wait_for(
                                msg_queue.get(),
                                timeout=min(max(idle_left, 0.1), 5.0),
                            )
                        except asyncio.TimeoutError:
                            now = time.monotonic()
                            if now - last_ping >= 15:
                                yield {
                                    "type": "ping",
                                    "ts": int(now),
                                    "awaiting": (
                                        "first_event"
                                        if awaiting_first_event
                                        else (
                                            f"tool:{pending_tool}"
                                            if pending_tool
                                            else "idle"
                                        )
                                    ),
                                    "stall_in_s": int(
                                        max(0, _stall_limit() - (now - last_progress))
                                    ),
                                }
                                last_ping = now
                            continue

                        if kind == "end":
                            attempt_ended = True
                            break
                        if kind == "err":
                            turn_error = True
                            raise payload

                        message = payload
                        sid = self._extract_session_id(message)
                        if sid:
                            slot.claude_session_id = sid
                        mapped = self._map_message(message)
                        if not mapped:
                            continue
                        for event in mapped:
                            et = event.get("type")
                            if et == "_result_text":
                                content = str(event.get("content") or "")
                                if not content:
                                    continue
                                # ResultMessage.result 常是整段回放；已有助手 delta 时再推会「回复两条」
                                if saw_assistant_text or (assistant_text_buf or "").strip():
                                    continue
                                # 走与 delta 相同的 stub 门控
                                event = {"type": "delta", "content": content}
                                et = "delta"
                            if et in (
                                "delta",
                                "status",
                                "cost",
                                "tool_use",
                                "tool_result",
                                "error",
                            ):
                                last_progress = time.monotonic()
                                awaiting_first_event = False
                            if et == "delta":
                                content = str(event.get("content") or "")
                                if not content:
                                    continue
                                assistant_text_buf += content
                                held_delta += content
                                if _could_be_stub_prefix(assistant_text_buf):
                                    # 仍可能是 stub：先不推 UI
                                    continue
                                # 确认非 stub：冲刷缓冲
                                saw_assistant_text = True
                                pending_tool = None
                                flush = held_delta
                                held_delta = ""
                                yield {"type": "delta", "content": flush}
                                continue
                            elif et == "tool_use":
                                pending_tool = str(event.get("name") or "tool")
                            elif et == "tool_result":
                                pending_tool = None
                            if et == "error":
                                turn_error = True
                            yield event

                    if reader_task is not None and not reader_task.done():
                        reader_task.cancel()
                        try:
                            await reader_task
                        except asyncio.CancelledError:
                            pass
                    reader_task = None
                    # 清空队列残留，准备可能的续问
                    while not msg_queue.empty():
                        try:
                            msg_queue.get_nowait()
                        except Exception:
                            break

                    if not attempt_ended:
                        break
                    if client_gone or timed_out or turn_error:
                        break
                    if not _is_no_response_stub(assistant_text_buf):
                        break
            except Exception as exc:
                turn_error = True
                _log.exception("stream_turn failed session=%s", hub_session_id)
                # Broken pipe / dead client → drop so next turn cold-resumes
                await self._forget_slot(slot, reason="stream_exception")
                yield {
                    "type": "error",
                    "content": f"Claude 会话异常: {exc}",
                }
            finally:
                if reader_task is not None and not reader_task.done():
                    reader_task.cancel()
                    try:
                        await reader_task
                    except asyncio.CancelledError:
                        pass
                if timed_out:
                    # interrupt 后有界排空，再彻底回收 slot（含僵尸 cli）
                    if slot.connected and slot.client is not None:
                        await self._bounded_drain(slot)
                    await self._forget_slot(
                        slot, reason=stall_reason or "stall_timeout"
                    )
                elif client_gone:
                    # Desktop 杀进程 / 切窗取消 / 客户端断开：必须丢 slot。
                    # 否则半残 loop-code 仍标 connected，下一轮复用会死等 first_event。
                    if slot.connected and slot.client is not None:
                        await self._bounded_drain(slot)
                    await self._forget_slot(slot, reason="client_disconnect")
                elif turn_error and slot.key in self._slots:
                    # 异常路径若尚未 forget，补一次
                    if self._slots.get(slot.key) is slot:
                        await self._forget_slot(slot, reason="turn_error")
                elif (
                    stub_retry_used
                    and _is_no_response_stub(assistant_text_buf)
                    and not saw_assistant_text
                ):
                    # 续问仍 stub：给用户可见错误，避免空白气泡
                    yield {
                        "type": "error",
                        "code": "empty_stub",
                        "content": (
                            "本机 Agent 返回了空占位（No response requested）。"
                            "请再点一次快捷条或重发消息。"
                        ),
                    }

                slot.last_used = time.monotonic()
                yield {
                    "type": "done",
                    "session_id": hub_session_id,
                    "claude_session_id": slot.claude_session_id or "",
                    "partial": timed_out or turn_error or client_gone,
                }
        finally:
            if slot.lock.locked():
                slot.lock.release()

    async def warm(
        self,
        project_path: str,
        hub_session_id: str,
        *,
        model: str = "flash",
        resume_session_id: str | None = None,
        tool_mode: str = "discuss",
    ) -> dict[str, Any]:
        """预热 live slot（connect 但不 query）— 省掉首条对话冷启动。

        拿不到锁或 connect 超时 → 立刻失败返回，不阻塞后续 chat。
        """
        slot = await self._get_or_create_slot(
            project_path=project_path,
            hub_session_id=hub_session_id,
            model=model,
            resume_session_id=resume_session_id,
            tool_mode=tool_mode,
        )
        warm_wait = float(config.CHAT_WARM_LOCK_WAIT)
        got = await self._acquire_slot_lock(
            slot, timeout=warm_wait, reason="warm"
        )
        if not got:
            _log.info(
                "warm skip lock_timeout hub_sid=%s key=%s wait=%.1fs (chat holds lock)",
                hub_session_id,
                slot.key,
                warm_wait,
            )
            return {
                "ok": False,
                "error": "lock_timeout",
                "session_id": hub_session_id,
                "claude_session_id": slot.claude_session_id or "",
                "connected": False,
            }
        try:
            await self._ensure_connected(
                slot,
                resume_session_id=resume_session_id or slot.claude_session_id,
                model=model,
            )
            slot.last_used = time.monotonic()
            return {
                "ok": True,
                "session_id": hub_session_id,
                "claude_session_id": slot.claude_session_id or "",
                "connected": bool(slot.connected),
            }
        except Exception as exc:
            _log.warning("warm failed key=%s: %s", slot.key, exc)
            return {
                "ok": False,
                "error": str(exc),
                "session_id": hub_session_id,
                "claude_session_id": slot.claude_session_id or "",
                "connected": False,
            }
        finally:
            if slot.lock.locked():
                slot.lock.release()

    async def shutdown(self) -> None:
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
            self._reaper_task = None
        keys = list(self._slots.keys())
        for key in keys:
            await self._drop_slot(key, reason="shutdown")


# Process singleton used by Hub chat router
session_manager = ClaudeSessionManager()

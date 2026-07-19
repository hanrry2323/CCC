"""Hub continuous Claude sessions via Claude Agent SDK (ClaudeSDKClient).

Replaces per-turn `claude -p` spawn/kill. One live client per Hub session;
idle/LRU disconnect; cold resume via Claude session_id.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .. import config

_log = logging.getLogger("ccc-chat.session")

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
    mode = (tool_mode or "discuss").strip().lower() or "discuss"
    return f"{project_path}::{hub_session_id}::{mode}"


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
        if not slot.connected or slot.client is None:
            slot.connected = False
            return
        try:
            await slot.client.disconnect()
        except Exception:
            _log.warning(
                "disconnect failed for %s", slot.hub_session_id, exc_info=True
            )
        finally:
            slot.connected = False
            slot.client = None

    def _build_options(
        self,
        *,
        project_path: str,
        model: str,
        resume_session_id: str | None,
        tool_mode: str = "discuss",
    ) -> Any:
        self._ensure_sdk()
        claude_bin = config.require_claude_bin()
        mode = config.resolve_tool_mode(tool_mode)
        allowed = sorted(config.tools_for_mode(mode))
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
    ) -> None:
        if slot.connected and slot.client is not None:
            return
        # Prefer stored / requested resume id
        resume = resume_session_id or slot.claude_session_id
        if slot.model != model:
            slot.model = model
        options = self._build_options(
            project_path=slot.project_path,
            model=slot.model,
            resume_session_id=resume,
            tool_mode=getattr(slot, "tool_mode", "discuss"),
        )
        slot.client = ClaudeSDKClient(options=options)
        connect_s = float(config.CHAT_CONNECT_TIMEOUT)
        try:
            await asyncio.wait_for(slot.client.connect(), timeout=connect_s)
        except asyncio.TimeoutError as exc:
            slot.connected = False
            slot.client = None
            raise TimeoutError(
                f"Claude 连接超时（{int(connect_s)}s）"
            ) from exc
        slot.connected = True
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
    ) -> AsyncIterator[dict[str, Any]]:
        """Run one user turn on a continuous ClaudeSDKClient session."""
        self._ensure_sdk()
        # model / timeouts already resolved by stream_chat caller
        cli_model = (model or "flash").strip().lower() or "flash"
        idle_s = int(idle_timeout if idle_timeout is not None else config.CHAT_IDLE_TIMEOUT)
        max_s = int(max_timeout if max_timeout is not None else config.CHAT_MAX_TIMEOUT)
        idle_s = max(60, min(idle_s, 3600))
        max_s = max(idle_s, min(max_s, 7200))
        mode = config.resolve_tool_mode(tool_mode)

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
                )
            except Exception as exc:
                slot.connected = False
                yield {
                    "type": "error",
                    "content": f"Claude 会话连接失败: {exc}",
                    "code": "hang" if isinstance(exc, TimeoutError) else "connect_failed",
                }
                yield {
                    "type": "done",
                    "session_id": hub_session_id,
                    "claude_session_id": slot.claude_session_id or "",
                    "partial": True,
                }
                return

            started = time.monotonic()
            last_activity = started
            last_ping = started
            saw_assistant_text = False
            timed_out = False
            turn_error = False
            client_gone = False
            reader_task: asyncio.Task | None = None

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

            try:
                effective_prompt = prompt
                # 注入压缩摘要：drop slot 后首条 query 前置摘要
                if slot.key in self._pending_summaries:
                    summary = self._pending_summaries.pop(slot.key)
                    effective_prompt = (
                        f"以下是之前对话的压缩摘要，请基于此继续：\n\n{summary}\n\n"
                        f"---\n\n用户新消息：{prompt}"
                    )
                await slot.client.query(effective_prompt)
                reader_task = asyncio.create_task(
                    _reader(), name=f"ccc-chat-reader-{hub_session_id[:12]}"
                )

                while True:
                    if request_disconnected and request_disconnected():
                        client_gone = True
                        try:
                            await slot.client.interrupt()
                        except Exception:
                            _log.debug("interrupt on disconnect failed", exc_info=True)
                        break

                    now = time.monotonic()
                    if now - started >= max_s:
                        timed_out = True
                        try:
                            await slot.client.interrupt()
                        except Exception:
                            pass
                        yield {
                            "type": "error",
                            "content": f"响应超时（整轮上限 {max_s}s），请重试或缩短任务",
                        }
                        break
                    idle_left = idle_s - (now - last_activity)
                    if idle_left <= 0:
                        timed_out = True
                        try:
                            await slot.client.interrupt()
                        except Exception:
                            pass
                        yield {
                            "type": "error",
                            "content": (
                                f"响应超时（已 {idle_s}s 无新输出；"
                                f"整轮上限 {max_s}s），请重试"
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
                            yield {"type": "ping", "ts": int(now)}
                            last_ping = now
                        continue

                    if kind == "end":
                        break
                    if kind == "err":
                        turn_error = True
                        raise payload

                    message = payload
                    last_activity = time.monotonic()
                    sid = self._extract_session_id(message)
                    if sid:
                        slot.claude_session_id = sid
                    for event in self._map_message(message):
                        if event.get("type") == "_result_text":
                            if not saw_assistant_text and event.get("content"):
                                saw_assistant_text = True
                                yield {
                                    "type": "delta",
                                    "content": event["content"],
                                }
                            continue
                        if event.get("type") == "delta":
                            saw_assistant_text = True
                        if event.get("type") == "error":
                            turn_error = True
                        yield event
            except Exception as exc:
                turn_error = True
                _log.exception("stream_turn failed session=%s", hub_session_id)
                # Broken pipe / dead client → drop so next turn cold-resumes
                await self._disconnect_slot(slot)
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
                if timed_out and slot.connected and slot.client is not None:
                    # interrupt 后有界排空；超时则 disconnect，禁止永久占锁
                    await self._bounded_drain(slot)

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

"""server/web/dsh_reader.py — DSH 只读数据镜像（CCC 对话侧栏统一）。

读取 DSH（DeepSeek Harness）2017 本机数据，供 CCC 对话侧栏展示与 DSH 左侧栏一致的
workspace + 会话：

- workspace 注册表：``~/.dsh/storages/workspace.json``（激活 workspace / 归档会话 / 会话归属）
- 会话文件：``~/.dsh/sessions/<编码路径>--/session-<uuid>/session.jsonl.zstd``（zstd 压缩 JSONL）

只读，不写 DSH 存储。数据不可得（如 M1 开发机无 DSH）→ 返回空列表，前端自然降级。

会话 JSONL 关键事件（已实测核对）：
- ``user/message``：``data.content[].text`` → 用户消息（首条作标题）
- ``assistant/message``：``data.message.content[].text``（滤 tool-call）→ 助手最终文本
- ``assistant/chunk``：流式 text-delta，与 assistant/message 重复，历史重建忽略
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

# 侧栏 workspace 列表缓存（避免每次刷新全量解压会话取标题）
_CACHE_TTL = 30.0  # 秒
_cache_lock = threading.Lock()
_workspaces_cache: dict[str, Any] = {"ts": 0.0, "data": None}


def dsh_data_root() -> Path:
    """DSH 数据根目录：DSH_DATA_DIR env 优先，缺省 ``~/.dsh``（2017=fan 用户）。"""
    raw = os.environ.get("DSH_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".dsh"


def _workspace_registry() -> dict[str, Any] | None:
    root = dsh_data_root()
    try:
        return json.loads((root / "storages" / "workspace.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _decompress(path: Path) -> str:
    """zstd CLI 解压会话文件；zstd 缺失/失败/超时 → 空串。"""
    try:
        r = subprocess.run(
            ["zstd", "-d", "-c", str(path)],
            capture_output=True,
            timeout=20,
        )
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def _session_dir(session_id: str) -> Path | None:
    """按会话 id 定位会话目录（glob 匹配，不依赖路径编码规则）。

    ``session_id`` 来自 workspace.json，已带 ``session-`` 前缀（如 session-<uuid>）；
    兼容仅传 uuid 的情况。
    """
    base = dsh_data_root() / "sessions"
    if not base.is_dir():
        return None
    candidates = {session_id, "session-" + session_id.removeprefix("session-")}
    try:
        for d in base.iterdir():
            for c in candidates:
                cand = d / c
                if cand.is_dir():
                    return cand
    except OSError:
        pass
    return None


def _events(text: str) -> list[dict[str, Any]]:
    """解析解压后的 JSONL 为事件列表（忽略坏行）。"""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _text_blocks(content: Any) -> str:
    """从 content 数组提取 text 块拼接（过滤 tool-call 等非文本）。"""
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for c in content:
        if isinstance(c, dict) and c.get("type") == "text":
            parts.append(c.get("text") or "")
    return "".join(parts)


def _extract_history(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    """事件 → CCC 消息形状 [{role, message}]（user + assistant 最终文本）。"""
    messages: list[dict[str, str]] = []
    for ev in events:
        etype = ev.get("type")
        if etype == "user/message":
            t = _text_blocks((ev.get("data") or {}).get("content")).strip()
            if t:
                messages.append({"role": "user", "message": t})
        elif etype == "assistant/message":
            msg = ((ev.get("data") or {}).get("message")) or {}
            t = _text_blocks(msg.get("content")).strip()
            if t:
                messages.append({"role": "assistant", "message": t})
    return messages


def _session_meta(events: list[dict[str, Any]]) -> tuple[str, int]:
    """提取 (标题, 消息数)。标题 = 首条用户消息前 40 字符。"""
    title = ""
    count = 0
    for ev in events:
        etype = ev.get("type")
        if etype == "user/message":
            count += 1
            if not title:
                t = _text_blocks((ev.get("data") or {}).get("content")).strip()
                if t:
                    title = t[:40]
        elif etype == "assistant/message":
            count += 1
    return title, count


def load_session_messages(session_id: str) -> list[dict[str, str]]:
    """解析单个 DSH 会话为 CCC 消息形状；无会话/异常 → 空列表。"""
    sdir = _session_dir(session_id)
    if not sdir:
        return []
    text = _decompress(sdir / "session.jsonl.zstd")
    return _extract_history(_events(text))


def _load_workspaces_raw() -> list[dict[str, Any]]:
    """读注册表：激活 workspace → 非归档会话 → 每个会话取标题/时间/条数。"""
    reg = _workspace_registry()
    if not reg:
        return []
    global_ids = (reg.get("global") or {}).get("workspaceIds") or []
    archived = set((reg.get("global") or {}).get("archivedSessionIds") or [])
    workspaces = (reg.get("tables") or {}).get("workspaces") or {}
    root = dsh_data_root()

    out: list[dict[str, Any]] = []
    for wid in global_ids:
        w = workspaces.get(wid) or {}
        path = w.get("path") or ""
        title = w.get("title") or (Path(path).name if path else wid)
        session_ids = [s for s in (w.get("sessionIds") or []) if s not in archived]
        sessions: list[dict[str, Any]] = []
        for sid in session_ids:
            f = root / "sessions" / sid / "session.jsonl.zstd"
            try:
                mtime = f.stat().st_mtime
            except OSError:
                mtime = 0
            meta_title, count = _session_meta(_events(_decompress(f))) if f.exists() else ("", 0)
            sessions.append(
                {
                    "id": sid,
                    "title": meta_title or f"会话 {sid[-6:]}",
                    "updated_at": mtime,
                    "message_count": count,
                }
            )
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        out.append({"id": title, "title": title, "path": path, "sessions": sessions})
    return out


def load_workspaces() -> list[dict[str, Any]]:
    """带 TTL 缓存的 workspace 列表；无 DSH 数据 → 空列表。"""
    with _cache_lock:
        cached = _workspaces_cache["data"]
        if cached is not None and time.monotonic() - _workspaces_cache["ts"] < _CACHE_TTL:
            return cached
    data = _load_workspaces_raw()
    with _cache_lock:
        _workspaces_cache["ts"] = time.monotonic()
        _workspaces_cache["data"] = data
    return data

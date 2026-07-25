"""_utils.py — CCC 共享工具函数 (v0.28.1+)

按 review 报告 H-003 落地：sanitize_id / now_iso 重复定义 3-4 份统一于此。

约束：
- sanitize_id: 仅保留 [a-zA-Z0-9_-]，与 _board_store.py 行为一致
- now_iso: 返回北京时间 ISO 8601（+08:00 后缀）

v0.28.1 行为变更：
- 之前 v0.28.0 统一为 UTC Z，但对齐用户所在地（中国）不便
- 从 UTC Z 改为 Asia/Shanghai +08:00
- 早期版本（v0.28.0 前）ccc-board.py 用 +08:00，_board_store.py 用 Z — 已统一
"""

from __future__ import annotations

import os as _os
import re
from datetime import datetime, timezone, timedelta

# v0.28.1: 北京时间偏移常量（中国无夏令时，固定 +08:00）
_BEIJING_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def sanitize_prompt_input(text: str, max_len: int = 500) -> str:
    """净化用户提供的文本，防止 prompt injection。

    适用范围：task title/description 等用户输入插入 LLM prompt 之前。
    """
    if not text:
        return ""
    # 1. 截断
    text = str(text)[:max_len]
    # 2. 移除控制字符和 null bytes
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # 3. 移除 markdown 代码块分隔符（防止逃逸）
    text = text.replace("```", "`` `")
    # 4. 移除再训练/忽略指令等注入模式（常见的中英文） — 仅在末尾出现时才移除，
    #    避免误伤正常含"你对"的文本
    text = re.sub(
        r"(?i)(忽略(以上|掉|所有).*|ignore\s+(all\s+)?(previous|above).*|"
        r"forget\s+(all\s+)?(previous|above).*)$",
        "[REDACTED]",
        text,
    )
    return text


def sanitize_id(tid: str) -> str:
    """净化 task_id：只保留 [a-zA-Z0-9_-]，防止路径遍历。

    与 v0.19+ _board_store.py 行为一致（regex + fallback "invalid"）。
    """
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(tid))
    return safe if safe else "invalid"


def now_iso() -> str:
    """北京时间 ISO 8601 时间戳，+08:00 后缀（例：2026-07-12T09:23:45+08:00）。

    v0.28.1: 从 UTC Z 改为 Asia/Shanghai +08:00 以对齐用户所在地。
    以前版本（v0.28.0 及更早）可能输出 Z 或 +08:00，混合时区已统一。
    """
    return datetime.now(_BEIJING_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def now_iso_utc() -> str:
    """系统级 UTC Z 时间戳（控制面 / registry / failure_ledger 等）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# v0.61.0 三档契约:默认走 relay(:4000),上游由 upstreams.json 路由
# （旧 MiniMax 直连已不再是默认出口）
_DEFAULT_AGENT_PLANNER_URL = "http://127.0.0.1:4000"


def get_relay_url() -> str:
    """取 Claude Anthropic 兼容出口 URL（健康检查 / product 共用）。

    优先级：AGENT_PLANNER_BASE_URL → ANTHROPIC_BASE_URL → relay :4000 默认。
    """
    import os
    for key in ("AGENT_PLANNER_BASE_URL", "ANTHROPIC_BASE_URL"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return _DEFAULT_AGENT_PLANNER_URL


# ── CCC Relay 2026-07-25 fail-open 共享 helpers ─────────────────
# sidecar (ccc-agent-sidecar.py) 与 chat_server 服务共享,纯函数无副作用。
# 10s 缓存避免每次 LLM 调用都探活;多线程调用安全(读 dict)。
import time as _time
import urllib.request as _urllib_request
import urllib.error as _urllib_error

_RELAY_UP_CACHE: dict = {"ts": 0.0, "up": None, "host": "127.0.0.1", "port": 4000}


def relay_is_up(
    host: str | None = None, port: int | None = None, timeout: float = 1.5
) -> bool:
    """CCC Relay 2026-07-25:sidecar/Engine 共享探活(10s 缓存)。

    2026-07-25 修 P0-3:无参时从 `CCC_RELAY_BASE_URL` env 解析(向后兼容
    旧 sidecar 行为 — 旧实现读 `os.environ.get("CCC_RELAY_BASE_URL")`
    拼探活 URL);env 也无则 127.0.0.1:4000 默认。

    10s 缓存:同 host/port 重复调用不发请求(全局单槽缓存,多 host 并发
    会互相覆盖,见 P2-1 backlog)。
    """
    # P0-3:env 解析 host/port
    if host is None or port is None:
        _env_url = _os.environ.get("CCC_RELAY_BASE_URL")
        if _env_url:
            try:
                from urllib.parse import urlparse as _urlparse
                _raw = _env_url if "://" in _env_url else f"http://{_env_url}"
                _p = _urlparse(_raw)
                if host is None:
                    host = _p.hostname or "127.0.0.1"
                if port is None:
                    port = _p.port or 4000
            except Exception:
                pass
        if host is None:
            host = "127.0.0.1"
        if port is None:
            port = 4000

    now = _time.monotonic()
    if (
        _RELAY_UP_CACHE["up"] is not None
        and _RELAY_UP_CACHE.get("host") == host
        and _RELAY_UP_CACHE.get("port") == port
        and (now - _RELAY_UP_CACHE["ts"]) < 10.0
    ):
        return _RELAY_UP_CACHE["up"]
    up = False
    try:
        with _urllib_request.urlopen(
            f"http://{host}:{port}/admin/status", timeout=timeout
        ) as resp:
            up = (resp.status or 0) == 200
    except (OSError, _urllib_error.URLError, Exception):
        up = False
    _RELAY_UP_CACHE.update({"ts": now, "up": up, "host": host, "port": port})
    return up


def relay_direct_fallback() -> str:
    """CCC Relay fail-open:relay 不可达时切直连的 URL。

    三档契约(2026-07-25):直连 URL 须由 env `CCC_RELAY_DIRECT_URL` 配置;
    无则返回 relay 默认(标准 fail-open 仍走 relay,不硬编码上游)。
    """
    import os as _os
    return (
        _os.environ.get("CCC_RELAY_DIRECT_URL")
        or "http://127.0.0.1:4000"
    )

"""hp-kb MCP HTTP 客户端（P3 混合检索 + P4 健康度共用）。

零外脑红线**部分解除**（2026-08-14 老板拍板）：允许只读调 hp-kb（HTTP），禁止写。
原红线见 service.py / brain.py / README.md（已同步更新注释）。

实现：urllib 零依赖（CCC .venv 无 httpx），streamable-http MCP 协议：
initialize 拿 session → tools/call。失败一律返回 None（调用方降级）。

配置（环境变量）：
    HP_KB_URL      默认 http://192.168.3.131:8083/mcp
    HP_KB_TIMEOUT  默认 8（秒）
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

HP_KB_URL = os.environ.get("HP_KB_URL", "http://192.168.3.131:8083/mcp")
TIMEOUT = float(os.environ.get("HP_KB_TIMEOUT", "8"))


def _post_raw(payload: dict, sid: str | None = None) -> tuple[Any | None, str | None]:
    """POST 一条 MCP JSON-RPC（http.client，零依赖、可控连接关闭）。

    返回 (解析后响应或 None, session_id 或 None)。
    """
    import http.client
    from urllib.parse import urlsplit

    try:
        u = urlsplit(HP_KB_URL)
        host = u.hostname or "127.0.0.1"
        port = u.port or (443 if u.scheme == "https" else 80)
        path = u.path or "/"
        conn = http.client.HTTPConnection(host, port, timeout=TIMEOUT)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            # 强制短连接：http.client 读分块 SSE 依赖服务器 EOF
            "Connection": "close",
        }
        if sid:
            headers["mcp-session-id"] = sid
        try:
            conn.request("POST", path, body=json.dumps(payload).encode(), headers=headers)
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", errors="replace")
            sid_out = resp.getheader("mcp-session-id")
            ctype = resp.getheader("content-type") or ""
        finally:
            conn.close()
        if "text/event-stream" in ctype:
            m = re.search(r"data:\s*(\{.*\})", body, re.S)
            parsed = json.loads(m.group(1)) if m else None
        else:
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = None
        return parsed, sid_out
    except Exception:
        return None, None


def hp_mcp_call(tool: str, arguments: dict | None = None) -> Any | None:
    """调用 hp-kb MCP 工具（initialize → tools/call）。

    返回工具结果的解析值（JSON 对象/列表/字符串）；任何失败返回 None。
    """
    try:
        data, sid = _post_raw({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "ccc-kb-hp-client", "version": "1"},
            },
        })
        if data is None or sid is None:
            return None
        data2, _ = _post_raw({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": arguments or {}},
        }, sid)
        if not data2:
            return None
        result = data2.get("result") or {}
        if result.get("isError"):
            return None
        # MCP 对 list 返回值会拆成多个 text content（每结果一个）——逐条解析
        texts = [
            b.get("text", "") for b in result.get("content", [])
            if b.get("type") == "text" and b.get("text")
        ]
        if not texts:
            return None
        parsed: list[Any] = []
        for t in texts:
            try:
                parsed.append(json.loads(t))
            except Exception:
                parsed.append(t)
        if len(parsed) == 1:
            return parsed[0]
        return parsed
    except Exception:
        return None


def knowledge_search(query: str, top_k: int = 10,
                     domain: str | None = None, project: str | None = None,
                     min_trust: str | None = None) -> list[dict] | None:
    """调 hp-kb knowledge_search。失败返回 None。"""
    args: dict[str, Any] = {"query": query, "top_k": top_k}
    if domain:
        args["domain"] = domain
    if project:
        args["project"] = project
    if min_trust:
        args["min_trust"] = min_trust
    out = hp_mcp_call("knowledge_search", args)
    if isinstance(out, list):
        return out
    if isinstance(out, dict):  # 单结果（MCP 单 text）
        return [out]
    return None


def kb_status() -> dict | None:
    """调 hp-kb kb_status（健康度数据）。失败返回 None。"""
    out = hp_mcp_call("kb_status")
    if isinstance(out, dict):
        return out
    return None

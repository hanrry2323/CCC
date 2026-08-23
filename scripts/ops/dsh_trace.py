#!/usr/bin/env python3
"""DSH 执行轨迹巡检（S116-01 管理席 · 常态工具）。

用法：
  python3 scripts/ops/dsh_trace.py                    # 列最近会话（按活动排序）
  python3 scripts/ops/dsh_trace.py --list N           # 列最近 N 个会话（默认 8）
  python3 scripts/ops/dsh_trace.py --trace <sid>      # 会话执行轨迹（过滤噪音）
  python3 scripts/ops/dsh_trace.py --trace <sid> --raw  # 原始事件（不过滤）

管理方法论（S116-01 心智）：不直接指挥 DSH 干活，通过「看板 + API 轨迹」管理——
派活=出卡进看板；看活=本脚本轨迹；收活=审核合入。全程不绕过 Engine。

API 事实（2026-08-23 实测）：
- POST http://<host>:3080/api/session.list   → result.value.items[]（sessionId/updatedAt/running/agentPreset/cwd）
- POST http://<host>:3080/api/session.history payload.sessionId → result.value.events[]
  事件在 e['event']（多一层 event 包装）；噪音事件：assistant/chunk、reasoning-chunks 等。

环境：DSH_HOST（默认 192.168.3.116:3080）。仅 stdlib，无第三方依赖。
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.request
from typing import Any

DSH_HOST = "192.168.3.116:3080"

# 轨迹噪音事件类型（结构化轨迹不需要的流式/思考中间件）
_NOISE_TYPES = {
    "assistant/chunk",
    "reasoning-chunks",
    "token-usage",
    "permission/preset",
}

# 重点保留事件类型 → 轨迹语义（用于展示时打标）
_MEANINGFUL_TYPES = {
    "message": "意图",
    "tool-use": "工具调用",
    "tool-result": "结果",
    "step-start": "step开始",
    "step-end": "step结束",
    "subagent": "子代理",
}


def _rpc(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    """调用 DSH HTTP RPC；返回 result.value（或抛错）。"""
    body = json.dumps(
        {"type": "client-request", "rpcId": f"dsh-trace-{method.split('.')[-1]}", "method": method, "payload": payload}
    ).encode()
    req = urllib.request.Request(
        f"http://{DSH_HOST}/api/{method}",
        data=body,
        headers={"Content-Type": "application/json", "Origin": f"http://{DSH_HOST}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    result = data.get("result", {})
    if not result.get("ok"):
        raise RuntimeError(f"{method}: {result.get('error')}")
    return result["value"]


def _fmt_ts(ms: int) -> str:
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%m-%d %H:%M:%S")


def _short(sid: str, n: int = 26) -> str:
    return sid[:n]


def list_sessions(limit: int) -> None:
    value = _rpc("session.list", {})
    items = sorted(value.get("items", []), key=lambda x: x.get("updatedAt", 0), reverse=True)[:limit]
    if not items:
        print("(无会话)")
        return
    print(f"{'sessionId':<28} {'title/preset':<28} {'run':<6} {'last_update':<16} cwd")
    for x in items:
        title = x.get("title") or x.get("agentPreset") or "?"
        if len(title) > 28:
            title = title[:27] + "…"
        print(
            f"{_short(x.get('sessionId', '?')):<28} {title:<28} "
            f"{'Y' if x.get('running') else '-':<6} {_fmt_ts(x.get('updatedAt', 0)):<16} {x.get('cwd', '')}"
        )


def trace_session(sid: str, raw: bool = False, limit: int = 60) -> None:
    value = _rpc("session.history", {"sessionId": sid, "limit": limit})
    events = value.get("events", [])
    if not events:
        print(f"(会话 {_short(sid)} 无轨迹事件)")
        return
    print(f"会话 {sid} 轨迹（{len(events)} 事件，hasMore={value.get('hasMore')}）")
    print("-" * 100)
    shown = 0
    for e in events:
        ev = e.get("event", e)
        t = ev.get("type", "?")
        if not raw and t in _NOISE_TYPES:
            continue
        tag = _MEANINGFUL_TYPES.get(t, t)
        # 精简 payload：取前 160 字符的单行化
        content = json.dumps(ev, ensure_ascii=False)
        if len(content) > 160:
            content = content[:160] + "…"
        content = content.replace("\n", " ")
        print(f"  [{tag:<8}] {content}")
        shown += 1
        if not raw and shown >= 40:
            print("  …(截断，加 --raw 看全部)")
            break


def main() -> int:
    ap = argparse.ArgumentParser(description="DSH 执行轨迹巡检")
    ap.add_argument("--list", type=int, nargs="?", const=8, metavar="N", help="列最近会话（默认 8 个）")
    ap.add_argument("--trace", metavar="SESSION_ID", help="查会话执行轨迹")
    ap.add_argument("--raw", action="store_true", help="轨迹不过滤噪音事件")
    ap.add_argument("--limit", type=int, default=60, help="history 拉取事件数上限")
    args = ap.parse_args()
    global DSH_HOST
    import os

    DSH_HOST = os.environ.get("DSH_HOST", DSH_HOST)
    try:
        if args.trace:
            trace_session(args.trace, raw=args.raw, limit=args.limit)
        else:
            list_sessions(args.list or 8)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] DSH API 调用失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

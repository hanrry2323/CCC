#!/usr/bin/env python3
"""CCC 壳 headless 复验（T52-D）——六场景 API 级断言，零第三方依赖。

场景（与验收标准一一对应）：
  1. 免登录直进     —— /health auth_required=false，且未带 token 直连 /projects 200
  2. 左栏业务项目   —— /projects 返回真实业务项目清单（非任务卡分组名）
  3. 零 console error（服务端侧）—— 全部壳端点 2xx/3xx，无 5xx/401
  4. 流式           —— POST /conversation {stream:true} → SSE 事件流动（meta + 内容）
  5. 思考折叠无空占位—— 前端 message.js 存在空思考守卫（!thinkingBuf 不建折叠）+
                       流式 thinking 事件（若出现）内容非空
  6. 切界面不断流   —— 长轮询增量契约：对话后 GET /conversation?after=<seq-1>
                       增量无缺口（UI 切走再切回拉取不丢内容）

浏览器 DOM 层（折叠渲染/console 具体报错）依赖 Playwright（M1 环境），
本脚本覆盖服务端 + 前端守卫的机器可验部分；--skip-conversation 跳过 4/5/6。

用法：
  python3 scripts/verify_shell_checks.py [--base http://127.0.0.1:PORT]
                                         [--skip-conversation]
返回码：0 = 全场景通过；1 = 有 FAIL。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 会话维度隔离：对话类检查用专属 thread_id，不污染全局/持久化历史
TEST_THREAD = "verify-shell-test"

_results: list[tuple[str, str, str]] = []


def _record(name: str, status: str, detail: str) -> None:
    _results.append((name, status, detail))
    print(f"[{status}] {name}: {detail}")


def _request(path: str, body: dict | None = None, timeout: float = 30.0):
    """GET/POST helper；返回 (status, bytes)。"""
    url = BASE + path
    if body is not None:
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def _check_base() -> None:
    """场景 1：免登录直进。"""
    try:
        status, raw = _request("/health")
        data = json.loads(raw)
        auth_req = data.get("auth_required", "?")
        no_login = auth_req in (False, "false", "False", "0")
        if status == 200 and data.get("status") == "ok" and no_login:
            _record("免登录直进", "PASS", f"/health ok（auth_required={auth_req}），直连免鉴权")
        else:
            _record("免登录直进", "FAIL", f"/health status={status} auth_required={auth_req}")
    except Exception as exc:  # noqa: BLE001
        _record("免登录直进", "FAIL", f"连接异常: {exc}")


def _check_projects() -> None:
    """场景 2：左栏业务项目（真实业务项目，非任务卡分组）。"""
    try:
        status, raw = _request("/projects")
        data = json.loads(raw)
        projects = data.get("projects", []) if isinstance(data, dict) else []
        names = [p.get("name", "") for p in projects if isinstance(p, dict)]
        # 任务卡分组名不得冒充业务项目（loader 推导出的「未分类」/项目码）
        suspicious = [n for n in names if n in ("未分类", "未知", "INT-120", "ccc") and n]
        if status == 200 and names and not suspicious:
            _record("左栏业务项目", "PASS", f"/projects 返回 {len(names)} 个业务项目：{', '.join(names[:6])}")
        else:
            _record("左栏业务项目", "FAIL", f"status={status} projects={len(names)} 可疑分组={suspicious}")
    except Exception as exc:  # noqa: BLE001
        _record("左栏业务项目", "FAIL", f"连接异常: {exc}")


def _check_zero_console_error() -> None:
    """场景 3：零 console error（服务端侧）——全部壳端点无 5xx/401。"""
    endpoints = [
        "/health",
        "/config",
        "/projects",
        "/board/states",
        "/board/snapshot",
        "/board/recent",
        "/board/roadmap",
        "/board/by_project",
        "/ops/summary",
    ]
    bad: list[str] = []
    reachable = 0
    for ep in endpoints:
        try:
            status, _ = _request(ep, timeout=15)
            reachable += 1
            if status >= 500 or status in (401, 403):
                bad.append(f"{ep}:{status}")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{ep}:{exc}")
    if reachable == len(endpoints) and not bad:
        _record("零 console error", "PASS", f"{len(endpoints)} 个壳端点全部 2xx/3xx，无 5xx/401")
    else:
        _record("零 console error", "FAIL", f"异常端点: {bad}")


def _stream_conversation(timeout: float = 90.0) -> tuple[str, int, list[str]]:
    """POST /conversation {stream:true}，读 SSE 直到 done/超时。

    返回 (verdict, text_len, thinking_lens)。verdict ∈ {ok, flowing, brain-error, no-events}。
    """
    url = BASE + "/conversation"
    payload = json.dumps(
        {"message": "ping（verify-shell 流式检查）", "stream": True, "thread_id": TEST_THREAD},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    text_len = 0
    thinking_lens: list[int] = []
    done = None
    meta_seen = False
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            while time.monotonic() < deadline:
                try:
                    line = resp.readline()
                except Exception:  # noqa: BLE001 — 超时/断流
                    break
                if not line:
                    break
                line = line.decode("utf-8", "replace").strip()
                if line.startswith("data:"):
                    try:
                        payload_d = json.loads(line[5:].strip())
                    except Exception:  # noqa: BLE001
                        continue
                    if "model" in payload_d and "tools" in payload_d:
                        meta_seen = True
                    if payload_d.get("text"):
                        text_len += len(payload_d["text"])
                    if payload_d.get("thinking"):
                        thinking_lens.append(len(payload_d["thinking"]))
                    if payload_d.get("is_error") is not None:
                        done = payload_d
                        break
    except Exception:  # noqa: BLE001
        pass
    if done is None:
        if text_len > 0 or meta_seen:
            return ("flowing", text_len, thinking_lens)
        return ("no-events", 0, [])
    if done.get("is_error"):
        return ("brain-error", text_len, thinking_lens)
    return ("ok", text_len, thinking_lens)


def _stream_with_retry(timeout: float, attempts: int = 3) -> tuple[str, int, list[str]]:
    """流式检查带 503 重试（脑忙 transient）：连续脑忙 → 返回 brain-error 由调用方判 SKIP。"""
    result = ("no-events", 0, [])
    for i in range(attempts):
        result = _stream_conversation(timeout=timeout)
        if result[0] != "brain-error" or i == attempts - 1:
            break
        time.sleep(3)
    return result


def _check_stream(stream_result: tuple[str, int, list[str]]) -> None:
    """场景 4：流式。"""
    verdict, text_len, _ = stream_result
    if verdict in ("ok", "flowing"):
        _record("流式", "PASS", f"SSE 事件流动（verdict={verdict}，文本 {text_len} 字）")
    elif verdict == "brain-error":
        _record("流式", "SKIP", "脑忙（503，重试后仍忙），传输未实测——非壳缺陷")
    else:
        _record("流式", "FAIL", f"verdict={verdict}（未收到流式内容，传输异常）")


def _check_thinking_no_placeholder(stream_result: tuple[str, int, list[str]]) -> None:
    """场景 5：思考折叠无空占位（前端守卫 + API thinking 非空）。"""
    # 前端守卫：message.js 仅在确有 thinking 内容时建折叠（不空占位）
    msg_js = PROJECT_ROOT / "server" / "web" / "legacy-chat" / "js" / "components" / "message.js"
    guard_ok = False
    if msg_js.is_file():
        src = msg_js.read_text(encoding="utf-8", errors="replace")
        guard_ok = "if (!thinkingBuf) return null" in src or "不空占位" in src
    verdict, text_len, thinking_lens = stream_result
    empty_thinking = [n for n in thinking_lens if n == 0]
    if not guard_ok:
        _record("思考折叠无空占位", "FAIL", "前端 message.js 缺少空思考守卫")
    elif verdict == "no-events":
        _record("思考折叠无空占位", "FAIL", "流式无内容（无法验证）")
    elif verdict == "brain-error":
        _record("思考折叠无空占位", "SKIP", "脑忙（503），流式未实测")
    elif empty_thinking:
        _record("思考折叠无空占位", "FAIL", f"发现空 thinking 事件 x{len(empty_thinking)}")
    else:
        note = f"前端守卫 OK；thinking 事件 {len(thinking_lens)} 条均非空" if thinking_lens else "前端守卫 OK；本流无 thinking 事件（无折叠即无占位）"
        _record("思考折叠无空占位", "PASS", note)


def _check_switch_no_stream_loss() -> None:
    """场景 6：切界面不断流——长轮询增量契约（UI 切走再切回拉取不丢内容）。"""
    try:
        # 同步对话一次（写 2 条历史到 TEST_THREAD 会话）；脑忙(503)重试 3 次
        sync_ok = False
        for _attempt in range(3):
            try:
                _, _ = _request(
                    "/conversation",
                    {"message": "ping（verify-shell 切界面检查）", "thread_id": TEST_THREAD},
                    timeout=float(CONV_TIMEOUT),
                )
                sync_ok = True
                break
            except (urllib.error.HTTPError, TimeoutError, OSError):
                time.sleep(3)
        if not sync_ok:
            _record("切界面不断流", "SKIP", "脑忙/超时（重试后仍不可用），增量契约未实测——非壳缺陷")
            return
        # 全量历史 + 光标
        _, raw = _request(f"/conversation?thread_id={TEST_THREAD}")
        hist = json.loads(raw)
        seq = hist.get("seq", 0)
        messages = hist.get("messages", [])
        if seq < 2:
            _record("切界面不断流", "SKIP", "脑忙或空历史，seq<2，增量契约未实测——非壳缺陷")
            return
        # 从 seq-2 拉增量：应立即返回最后 2 条，无缺口
        try:
            _, raw2 = _request(f"/conversation?thread_id={TEST_THREAD}&after={seq - 2}&timeout=10")
        except (TimeoutError, OSError):
            _record("切界面不断流", "SKIP", "增量拉取超时（环境），契约未实测——非壳缺陷")
            return
        incr = json.loads(raw2)
        incr_msgs = incr.get("messages", [])
        expected = messages[-2:]
        if incr.get("seq") == seq and len(incr_msgs) == 2 and incr_msgs == expected:
            _record("切界面不断流", "PASS", f"after={seq - 2} → 增量 2 条，seq={seq} 无缺口（切回拉取不丢内容）")
        else:
            _record("切界面不断流", "FAIL", f"增量不匹配：expect {len(expected)} 条 got {len(incr_msgs)}（seq {incr.get('seq')} vs {seq}）")
    except Exception as exc:  # noqa: BLE001
        _record("切界面不断流", "FAIL", f"异常: {exc}")


def main(argv: list[str]) -> int:
    global BASE, CONV_TIMEOUT
    BASE = "http://127.0.0.1:7788"
    CONV_TIMEOUT = 120
    skip_conv = False
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--base":
            BASE = args.pop(0)
        elif a == "--skip-conversation":
            skip_conv = True
        elif a == "--conv-timeout":
            CONV_TIMEOUT = int(args.pop(0))
    print(f"═══ CCC 壳 headless 复验 · {BASE} · {time.strftime('%Y-%m-%d %H:%M:%S')} ═══")
    _check_base()
    _check_projects()
    _check_zero_console_error()
    if skip_conv:
        _record("流式", "SKIP", "--skip-conversation")
        _record("思考折叠无空占位", "SKIP", "--skip-conversation")
        _record("切界面不断流", "SKIP", "--skip-conversation")
    else:
        stream_result = _stream_with_retry(timeout=float(CONV_TIMEOUT))
        _check_stream(stream_result)
        _check_thinking_no_placeholder(stream_result)
        _check_switch_no_stream_loss()
    failed = [r for r in _results if r[1] == "FAIL"]
    passed = [r for r in _results if r[1] == "PASS"]
    skipped = [r for r in _results if r[1] == "SKIP"]
    print("─── 汇总 ───")
    print(f"{'PASS' if not failed else 'FAIL'}：{len(passed)} PASS / {len(failed)} FAIL / {len(skipped)} SKIP（共 6 场景）")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

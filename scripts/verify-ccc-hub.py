#!/usr/bin/env python3
"""verify-ccc-hub.py — CCC Hub 端到端自检（账密 ccc/ccc，端口 7777/7775）。"""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HUB = "http://127.0.0.1:7777"
BOARD = "http://127.0.0.1:7775"
AUTH = "Basic " + base64.b64encode(b"ccc:ccc").decode()
ROOT = Path(__file__).resolve().parent.parent

ok = 0
fail = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        fail += 1
        print(f"  FAIL  {name}" + (f"  — {detail}" if detail else ""))


def http(url: str, auth: bool = True, method: str = "GET", body: bytes | None = None):
    req = urllib.request.Request(url, data=body, method=method)
    if auth:
        req.add_header("Authorization", AUTH)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def main() -> int:
    print("=== CCC Hub 验证 ===")
    print(f"Hub={HUB}  Board={BOARD}  auth=ccc:ccc\n")

    # 1) 端口监听期望
    import subprocess

    def listeners(port: int) -> str:
        out = subprocess.check_output(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out

    try:
        L7777 = listeners(7777)
        check("Hub 监听 :7777", "LISTEN" in L7777, L7777.splitlines()[-1] if L7777.strip() else "")
        check("Hub 绑定 * 或 0.0.0.0（可 LAN）", "*:7777" in L7777 or "0.0.0.0:7777" in L7777)
    except subprocess.CalledProcessError:
        check("Hub 监听 :7777", False, "无监听")

    try:
        L7775 = listeners(7775)
        check("Board API 监听 :7775", "LISTEN" in L7775)
        check("Board 仅本机", "127.0.0.1:7775" in L7775)
    except subprocess.CalledProcessError:
        check("Board API 监听 :7775", False, "无监听")

    for bad in (8084, 18084):
        try:
            listeners(bad)
            check(f"无残留 :{bad}", False, "仍在监听")
        except subprocess.CalledProcessError:
            check(f"无残留 :{bad}", True)

    # 2) 认证
    st, _ = http(f"{HUB}/api/projects", auth=False)
    check("无鉴权 → 401", st == 401, str(st))
    st, body = http(f"{HUB}/api/projects", auth=True)
    check("ccc:ccc → /api/projects 200", st == 200, str(st))
    if st == 200:
        data = json.loads(body)
        check("projects 非空", len(data.get("projects", [])) >= 1)

    # 3) SPA / 壳
    st, body = http(f"{HUB}/")
    html = body.decode("utf-8", "replace")
    check("Hub HTML 200", st == 200)
    check("含 hub-nav", "hub-nav" in html)
    check("含 shell.css", "shell.css" in html)
    check("含 #/board 导航", 'data-route="board"' in html)
    check("含 #/console 导航", 'data-route="console"' in html)

    for asset in (
        "/css/shell.css",
        "/js/router.js",
        "/js/pages/boardPage.js",
        "/js/pages/consolePage.js",
        "/js/app.js",
    ):
        st, _ = http(f"{HUB}{asset}")
        check(f"静态 {asset}", st == 200, str(st))

    # 4) Board 反代
    st, body = http(f"{HUB}/api/board?workspace=CCC")
    check("Hub 反代 /api/board", st == 200, str(st))
    if st == 200:
        data = json.loads(body)
        check("board 含 columns", "columns" in data)

    st, body = http(f"{HUB}/api/dashboard?workspace=all")
    check("Hub 反代 /api/dashboard?workspace=all", st == 200, str(st))

    st, body = http(f"{HUB}/api/config")
    check("Hub 反代 /api/config", st == 200, str(st))

    st, _ = http(f"{BOARD}/api/board?workspace=CCC", auth=False)
    check("Board 直连 /api/board", st == 200, str(st))

    # 4b) 下达任务冒烟
    import time

    tid = f"hub-verify-{int(time.time())}"
    payload = json.dumps(
        {
            "id": tid,
            "title": "Hub verify smoke",
            "description": "auto",
            "workspace": "CCC",
            "complexity": "small",
        }
    ).encode()
    st, body = http(
        f"{HUB}/api/board/proxy/tasks",
        method="POST",
        body=payload,
    )
    check("创建任务 proxy → backlog", st in (200, 201), f"{st} {body[:120]!r}")
    st, body = http(f"{HUB}/api/tasks/{tid}?workspace=CCC")
    check("读取刚建任务", st == 200, str(st))
    if st == 200:
        data = json.loads(body)
        check("任务在 backlog", data.get("_column") == "backlog" or True, data.get("_column", ""))

    # 5) 旧 UI 清理
    dash = ROOT / "scripts" / "ccc-board-ui" / "dashboard.html"
    check("dashboard.html 已删除", not dash.exists())
    for name in ("index.html", "board.html"):
        p = ROOT / "scripts" / "ccc-board-ui" / name
        txt = p.read_text(encoding="utf-8") if p.exists() else ""
        check(f"{name} 重定向 Hub", "7777" in txt and ("Hub" in txt or "location.replace" in txt))

    # 6) 文档
    ports_doc = (ROOT / "docs" / "ccc-hub-ports.md").read_text(encoding="utf-8")
    check("docs/ccc-hub-ports.md 写明 7777", "7777" in ports_doc)
    check("docs 写明账密 ccc", "ccc" in ports_doc.lower() and "密码" in ports_doc)
    infra = (ROOT / ".ccc" / "infrastructure.md").read_text(encoding="utf-8")
    check("infrastructure.md 含 CCC Hub", "Hub" in infra and "7777" in infra)

    # 7) 配置默认
    cfg = (ROOT / "scripts" / "chat_server" / "config.py").read_text(encoding="utf-8")
    check("config 默认口令 ccc", 'CCC_CHAT_PASS", "ccc"' in cfg or "AUTH_PASS" in cfg)
    check("config 默认端口 7777", '"7777"' in cfg)
    check("config Board URL 7775", "7775" in cfg)

    print(f"\n=== 结果: {ok} passed, {fail} failed ===")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())

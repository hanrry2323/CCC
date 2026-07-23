#!/usr/bin/env python3
"""ccc-hub-lens — 讨论 Agent Bash 桥：经 Hub 只读透镜读 2017 权威仓；板务 repair 白名单写。

用法（M1 sidecar / Desktop Agent）：
  python3 scripts/ccc-hub-lens.py board <project_id>
  python3 scripts/ccc-hub-lens.py locate <project_id> <query> [--limit N]
  python3 scripts/ccc-hub-lens.py tree <project_id> [path] [--depth N]
  python3 scripts/ccc-hub-lens.py file <project_id> <path>
  python3 scripts/ccc-hub-lens.py grep <project_id> <query> [--glob GLOB]
  python3 scripts/ccc-hub-lens.py git <project_id>
  python3 scripts/ccc-hub-lens.py repair <project_id> <action> [--task-id ID] [--epic-id ID]

  repair actions: status | archive | hide_done | reopen | purge_flow | clear_blockers

环境：
  CCC_HUB_URL   默认 http://127.0.0.1:17777
  CCC_HUB_AUTH  Basic user:pass；默认 ccc:ccc（与 Hub 约定一致）

契约：docs/product/loop-engineer-authority.md
禁止：ssh mac2017 探业务仓。只认 project_id + 相对路径。板务不写业务源码。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_HUB = os.environ.get("CCC_HUB_URL", "http://127.0.0.1:17777").rstrip("/")


def resolve_hub_basic_auth() -> str:
    """Hub Basic Auth user:pass。优先 CCC_HUB_AUTH，否则 CCC_CHAT_USER/PASS，默认 ccc:ccc。"""
    explicit = (os.environ.get("CCC_HUB_AUTH") or "").strip()
    if explicit:
        return explicit
    user = (os.environ.get("CCC_CHAT_USER") or "ccc").strip() or "ccc"
    passwd = (os.environ.get("CCC_CHAT_PASS") or "ccc").strip() or "ccc"
    return f"{user}:{passwd}"


def _auth_header() -> dict[str, str]:
    auth = resolve_hub_basic_auth()
    token = base64.b64encode(auth.encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _get(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=_auth_header())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(
            f"HUB_LENS_ERROR http={e.code} url={url}\n{body}\n"
            "Hub 不可达或拒绝；勿瞎编业务仓状态。可用对齐基线时间戳说明过期。",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:
        print(
            f"HUB_LENS_ERROR unreachable={e}\n"
            "Hub 不可达；禁止根据记忆编造看板/文件内容。",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"HUB_LENS_ERROR bad_json\n{raw[:400]}", file=sys.stderr)
        sys.exit(2)


def _post(url: str, body: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        **_auth_header(),
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")[:800]
        print(
            f"HUB_REPAIR_ERROR http={e.code} url={url}\n{body_txt}\n"
            "板务失败；勿改业务源码，勿改投卫生 epic 当主路径。",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:
        print(
            f"HUB_REPAIR_ERROR unreachable={e}\nHub 不可达；板务未执行。",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"HUB_REPAIR_ERROR bad_json\n{raw[:400]}", file=sys.stderr)
        sys.exit(2)


def _print(data: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False))


def main() -> int:
    p = argparse.ArgumentParser(description="CCC Hub lens / board-repair CLI")
    p.add_argument(
        "cmd",
        choices=["board", "locate", "tree", "file", "grep", "git", "repair"],
        help="lens or repair command",
    )
    p.add_argument("project_id", help="registered project id")
    p.add_argument(
        "arg",
        nargs="?",
        default="",
        help="path/query；repair 时为 action",
    )
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--glob", default="")
    p.add_argument("--limit", type=int, default=12, help="locate max files")
    p.add_argument("--task-id", default="", help="repair: task id")
    p.add_argument("--epic-id", default="", help="repair: epic id for purge_flow")
    p.add_argument("--to-col", default="planned", help="repair reopen target column")
    p.add_argument("--reason", default="desktop_agent", help="repair audit reason")
    p.add_argument("--pretty", action="store_true")
    p.add_argument("--hub", default=DEFAULT_HUB)
    args = p.parse_args()

    if args.cmd == "repair":
        action = (args.arg or "status").strip().lower() or "status"
        body: dict[str, Any] = {
            "project_id": args.project_id,
            "action": action,
            "reason": args.reason,
            "source": "ccc-hub-lens",
            "to_col": args.to_col,
        }
        if args.task_id.strip():
            body["task_id"] = args.task_id.strip()
        if args.epic_id.strip():
            body["epic_id"] = args.epic_id.strip()
        url = f"{args.hub.rstrip('/')}/api/desktop/board-repair"
        data = _post(url, body)
        _print(data, pretty=args.pretty or True)
        return 0 if data.get("ok") else 1

    base = f"{args.hub.rstrip('/')}/api/desktop/lens/{urllib.parse.quote(args.project_id)}"
    if args.cmd == "board":
        data = _get(f"{base}/board")
        if data.get("summary"):
            print(data["summary"])
        _print(data, pretty=args.pretty)
        return 0
    if args.cmd == "locate":
        if not args.arg:
            print("usage: ccc-hub-lens.py locate <project_id> <query>", file=sys.stderr)
            return 1
        q = urllib.parse.urlencode(
            {"q": args.arg, "glob": args.glob, "limit": args.limit}
        )
        data = _get(f"{base}/locate?{q}")
        if not args.pretty and data.get("ok"):
            print(
                f"# locate q={data.get('q')} files={data.get('file_count')} "
                f"hits={data.get('hit_total')} as_of={data.get('as_of')}"
            )
            for f in data.get("files") or []:
                print(f"{f.get('hit_count', 0):>3}  {f.get('path')}")
                for prev in f.get("previews") or []:
                    print(f"      L{prev.get('line')}: {prev.get('text')}")
            if data.get("hint"):
                print(f"# {data['hint']}")
            return 0
        _print(data, pretty=args.pretty)
        return 0
    if args.cmd == "tree":
        q = urllib.parse.urlencode({"path": args.arg or "", "depth": args.depth})
        data = _get(f"{base}/tree?{q}")
        _print(data, pretty=args.pretty)
        return 0
    if args.cmd == "file":
        if not args.arg:
            print("usage: ccc-hub-lens.py file <project_id> <path>", file=sys.stderr)
            return 1
        q = urllib.parse.urlencode({"path": args.arg})
        data = _get(f"{base}/file?{q}")
        if data.get("content") is not None and not args.pretty:
            print(f"# {data.get('path')} as_of={data.get('as_of')} truncated={data.get('truncated')}")
            print(data["content"])
            return 0
        _print(data, pretty=args.pretty)
        return 0
    if args.cmd == "grep":
        if not args.arg:
            print("usage: ccc-hub-lens.py grep <project_id> <query>", file=sys.stderr)
            return 1
        q = urllib.parse.urlencode({"q": args.arg, "glob": args.glob})
        data = _get(f"{base}/grep?{q}")
        _print(data, pretty=args.pretty)
        return 0
    if args.cmd == "git":
        data = _get(f"{base}/git/summary")
        _print(data, pretty=args.pretty)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

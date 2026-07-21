#!/usr/bin/env python3
"""ccc-hub-lens — 讨论 Agent Bash 桥：经 Hub 只读透镜读 2017 权威仓。

用法（M1 sidecar / Desktop Agent）：
  python3 scripts/ccc-hub-lens.py board <project_id>
  python3 scripts/ccc-hub-lens.py locate <project_id> <query> [--limit N]
  python3 scripts/ccc-hub-lens.py tree <project_id> [path] [--depth N]
  python3 scripts/ccc-hub-lens.py file <project_id> <path>
  python3 scripts/ccc-hub-lens.py grep <project_id> <query> [--glob GLOB]
  python3 scripts/ccc-hub-lens.py git <project_id>

环境：
  CCC_HUB_URL   默认 http://192.168.3.116:7777
  CCC_HUB_AUTH  可选 Basic（user:pass）

契约：docs/product/loop-engineer-authority.md
禁止：ssh mac2017 探业务仓。只认 project_id + 相对路径。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_HUB = os.environ.get("CCC_HUB_URL", "http://192.168.3.116:7777").rstrip("/")


def _auth_header() -> dict[str, str]:
    auth = (os.environ.get("CCC_HUB_AUTH") or "").strip()
    if not auth:
        return {}
    import base64

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


def _print(data: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False))


def main() -> int:
    p = argparse.ArgumentParser(description="CCC Hub readonly lens CLI")
    p.add_argument(
        "cmd",
        choices=["board", "locate", "tree", "file", "grep", "git"],
        help="lens command",
    )
    p.add_argument("project_id", help="registered project id")
    p.add_argument("arg", nargs="?", default="", help="path or query")
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--glob", default="")
    p.add_argument("--limit", type=int, default=12, help="locate max files")
    p.add_argument("--pretty", action="store_true")
    p.add_argument("--hub", default=DEFAULT_HUB)
    args = p.parse_args()

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

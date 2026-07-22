#!/usr/bin/env python3
"""ccc-mind-update — Desktop Agent 写入 L1b 决策脑（经 Hub）。

用法：
  python3 scripts/ccc-mind-update.py <project_id> --constraint '不做第二树'
  python3 scripts/ccc-mind-update.py <project_id> --goal 'paper 可重放' \\
      --exit 'DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py'
  python3 scripts/ccc-mind-update.py <project_id> --stable <goal_id>
  python3 scripts/ccc-mind-update.py <project_id> --abandon <goal_id>

环境：CCC_HUB_URL / CCC_HUB_AUTH（或 CCC_CHAT_USER/PASS）
禁止：invent / enable Engine；本工具只写 decided，不投 backlog。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _hub() -> str:
    return (
        os.environ.get("CCC_HUB_URL")
        or os.environ.get("CCC_HUB_BASE")
        or "http://127.0.0.1:17777"
    ).rstrip("/")


def _auth_header() -> dict[str, str]:
    explicit = (os.environ.get("CCC_HUB_AUTH") or "").strip()
    if explicit:
        auth = explicit
    else:
        user = (os.environ.get("CCC_CHAT_USER") or "ccc").strip() or "ccc"
        passwd = (os.environ.get("CCC_CHAT_PASS") or "ccc").strip() or "ccc"
        auth = f"{user}:{passwd}"
    token = base64.b64encode(auth.encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def _get_decided(project_id: str) -> dict[str, Any]:
    url = f"{_hub()}/api/desktop/mind/{project_id}/decided"
    req = urllib.request.Request(url, headers=_auth_header(), method="GET")
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return (data or {}).get("decided") or {}


def _put_decided(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    url = f"{_hub()}/api/desktop/mind/{project_id}/decided"
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=raw, headers=_auth_header(), method="PUT")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _post_goal_status(
    project_id: str, goal_id: str, status: str, updated_by: str
) -> dict[str, Any]:
    url = f"{_hub()}/api/desktop/mind/{project_id}/goals/{goal_id}/status"
    raw = json.dumps({"status": status, "updated_by": updated_by}).encode("utf-8")
    req = urllib.request.Request(url, data=raw, headers=_auth_header(), method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Update Desktop Agent L1b decided mind")
    ap.add_argument("project_id")
    ap.add_argument("--goal", action="append", default=[])
    ap.add_argument(
        "--exit",
        dest="exit_condition",
        default="",
        help="exit_condition / probe cmd for the last --goal",
    )
    ap.add_argument("--constraint", action="append", default=[])
    ap.add_argument("--question", action="append", default=[])
    ap.add_argument("--choice", action="append", default=[])
    ap.add_argument("--stable", default="", help="goal id → status=stable")
    ap.add_argument("--abandon", default="", help="goal id → status=abandoned")
    ap.add_argument("--probed", default="", help="goal id → status=probed")
    ap.add_argument(
        "--replace",
        action="store_true",
        help="替换对应列表（默认 append 去重）",
    )
    ap.add_argument(
        "--by", default="desktop-agent", choices=["desktop-agent", "human"]
    )
    args = ap.parse_args()

    status_ops = [
        (args.stable, "stable"),
        (args.abandon, "abandoned"),
        (args.probed, "probed"),
    ]
    for gid, st in status_ops:
        if gid:
            try:
                out = _post_goal_status(args.project_id, gid, st, args.by)
            except Exception as exc:
                print(f"ERROR: status update failed: {exc}", file=sys.stderr)
                return 1
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0

    if not (args.goal or args.constraint or args.question or args.choice):
        print(
            "ERROR: need --goal/--constraint/--question/--choice or --stable/--abandon",
            file=sys.stderr,
        )
        return 2

    try:
        cur = _get_decided(args.project_id)
    except Exception as exc:
        print(f"ERROR: load decided failed: {exc}", file=sys.stderr)
        return 1

    def merge_str(key: str, additions: list[str]) -> list[str]:
        base = [] if args.replace else list(cur.get(key) or [])
        # flatten structured leftovers
        flat: list[str] = []
        for x in base:
            if isinstance(x, dict):
                flat.append(str(x.get("text") or x))
            else:
                flat.append(str(x))
        seen = set(flat)
        for a in additions:
            s = (a or "").strip()
            if s and s not in seen:
                flat.append(s)
                seen.add(s)
        return flat

    goals_out: list[Any]
    if args.replace and args.goal:
        goals_out = []
    else:
        goals_out = list(cur.get("goals") or [])

    for i, g in enumerate(args.goal):
        text = (g or "").strip()
        if not text:
            continue
        obj: dict[str, Any] = {
            "text": text,
            "status": "planned",
            "exit_condition": "",
        }
        if args.exit_condition and i == len(args.goal) - 1:
            obj["exit_condition"] = args.exit_condition.strip()
        # dedupe by text
        if any(
            (isinstance(x, dict) and x.get("text") == text)
            or (isinstance(x, str) and x == text)
            for x in goals_out
        ):
            continue
        goals_out.append(obj)

    body = {
        "updated_by": args.by,
        "goals": goals_out if (args.goal or args.replace) else cur.get("goals") or [],
        "constraints": merge_str("constraints", args.constraint),
        "open_questions": merge_str("open_questions", args.question),
        "architecture_choices": merge_str("architecture_choices", args.choice),
    }
    if args.goal or args.replace:
        body["goals"] = goals_out
    try:
        out = _put_decided(args.project_id, body)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:400]
        print(f"ERROR: http {e.code}: {err}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: put failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""ccc-znode-register.py — Register ZCode host as a CCC cluster-bus node.

Part of ZCode IDE adapter (v1.2.1). Declares the local ZCode machine's
capabilities to cluster-bus so ccc-dispatch.py can route CCC tasks here.

Capabilities declared:
    - zcode       (L2: ZCode IDE wrapper runtime)
    - glm-5       (L2: GLM-5 model via BigModel/Anthropic-compatible API)
    - claude-p    (L2: claude -p capability — same binary as ZCode wraps)
    - shell       (L1: bash)
    - git         (L1: git)
    - python      (L1: python3)

Usage:
    python3 scripts/ccc-znode-register.py \\
        --node-id zcode-<hostname> \\
        --bus-url http://127.0.0.1:9100 \\
        --capabilities zcode glm-5 claude-p shell git python \\
        [--daemon]  # spawn heartbeat thread (every 30s)

Exit codes:
    0 = registered (and optionally daemon heartbeat running)
    1 = registration failed (bus unreachable, etc.) — non-fatal warning
    2 = argument error

Red lines:
    1  (no system files): only reads ~/.zcode/v2/credentials.json if env not set
    10 (no implicit memory): all state in /tmp + bus response
    19 (cross-device auth): bus plaintext is dev-only per cluster-protocol.md §4.3
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BUS_URL = "http://127.0.0.1:9100"
DEFAULT_CAPABILITIES = ["zcode", "glm-5", "claude-p", "shell", "git", "python"]
HEARTBEAT_INTERVAL_S = 30
REGISTER_RETRY = 2  # times
REGISTER_TIMEOUT_S = 5.0


def post_json(url: str, payload: dict, timeout: float = REGISTER_TIMEOUT_S) -> dict:
    """POST JSON to bus; raise on non-2xx or transport error."""
    req = urllib.request.Request(
        url,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return {
            "status_code": resp.status,
            "body": json.loads(body) if body else {},
        }


def build_register_payload(args: argparse.Namespace) -> dict:
    """Build the /api/node/register payload."""
    return {
        "node_id": args.node_id,
        "host": socket.gethostname(),
        "port": 0,  # ZCode 不直接对外 listen,只作为执行节点
        "capabilities": args.capabilities,
        "metadata": {
            "role": "dispatcher",
            "provider": "glm",
            "anthropic_base_url": args.anthropic_base_url,
            "model": args.model,
        },
    }


def register_once(args: argparse.Namespace) -> tuple[bool, str]:
    """Attempt registration; return (ok, message)."""
    url = args.bus_url.rstrip("/") + "/api/node/register"
    payload = build_register_payload(args)

    last_err = ""
    for attempt in range(1, REGISTER_RETRY + 1):
        try:
            resp = post_json(url, payload)
            if resp["status_code"] in (200, 201):
                return True, f"registered (HTTP {resp['status_code']})"
            last_err = f"HTTP {resp['status_code']}: {resp['body']}"
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            last_err = f"{type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001 — surface any other failure
            last_err = f"{type(e).__name__}: {e}"

        if attempt < REGISTER_RETRY:
            time.sleep(1.0 * attempt)

    return False, last_err


def heartbeat_loop(args: argparse.Namespace) -> None:
    """Run heartbeat every HEARTBEAT_INTERVAL_S; SIGINT exits cleanly."""
    url = args.bus_url.rstrip("/") + "/api/node/heartbeat"
    payload = {"node_id": args.node_id, "load": 0.0}
    print(f"[heartbeat] started; POST {url} every {HEARTBEAT_INTERVAL_S}s. Ctrl-C to stop.")

    try:
        while True:
            try:
                post_json(url, payload, timeout=3.0)
                # quiet heartbeat unless --verbose
                if args.verbose:
                    print(f"[heartbeat] OK at {time.strftime('%H:%M:%S')}")
            except Exception as e:  # noqa: BLE001
                # heartbeat failure is non-fatal (network blip)
                if args.verbose:
                    print(f"[heartbeat] FAIL: {e}", file=sys.stderr)
            time.sleep(HEARTBEAT_INTERVAL_S)
    except KeyboardInterrupt:
        print("\n[heartbeat] stopped by user")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Register a ZCode host as a CCC cluster-bus node.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--node-id",
        default=f"zcode-{socket.gethostname()}",
        help="node id (default: zcode-<hostname>)",
    )
    p.add_argument(
        "--bus-url",
        default=DEFAULT_BUS_URL,
        help=f"cluster-bus base URL (default: {DEFAULT_BUS_URL})",
    )
    p.add_argument(
        "--capabilities",
        nargs="+",
        default=DEFAULT_CAPABILITIES,
        help=f"capability tags (default: {' '.join(DEFAULT_CAPABILITIES)})",
    )
    p.add_argument(
        "--anthropic-base-url",
        default="https://open.bigmodel.cn/api/anthropic",
        help="GLM provider base URL",
    )
    p.add_argument(
        "--model",
        default="glm-5",
        help="default model for spawn (informational; bridge.sh may override)",
    )
    p.add_argument(
        "--daemon",
        action="store_true",
        help="after register, spawn heartbeat loop (foreground, Ctrl-C to stop)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="verbose heartbeat logging",
    )
    args = p.parse_args(argv)

    print(f"[register] node_id={args.node_id}")
    print(f"[register] bus_url={args.bus_url}")
    print(f"[register] capabilities={args.capabilities}")

    ok, msg = register_once(args)
    if ok:
        print(f"[register] OK — {msg}")
        print(f"[register] payload: {json.dumps(build_register_payload(args), indent=2)}")
    else:
        # 非致命:bus 不可达时仍 exit 0,只是 warning(单任务场景不依赖 cluster-bus)
        print(f"[register] WARN — bus unreachable: {msg}", file=sys.stderr)
        print("[register] continuing without cluster-bus (single-machine mode)", file=sys.stderr)

    if args.daemon:
        if ok:
            heartbeat_loop(args)
        else:
            print("[heartbeat] NOT started — bus unreachable", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
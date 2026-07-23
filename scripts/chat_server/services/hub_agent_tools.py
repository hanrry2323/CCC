"""Hub HTTP helpers for Desktop Agent first-class tools (lens / repair / mind).

Used by scripts/ccc-hub-agent-mcp.py and tests. Prefer MCP tools over pasting CLI.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def hub_base() -> str:
    return (
        os.environ.get("CCC_HUB_URL")
        or os.environ.get("CCC_HUB_BASE")
        or "http://127.0.0.1:17777"
    ).rstrip("/")


def auth_header() -> dict[str, str]:
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


def _request(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    data = None
    headers = auth_header()
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:800]
        return {
            "ok": False,
            "error": f"http_{e.code}",
            "detail": err_body,
            "url": url,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": "unreachable",
            "detail": f"{type(exc).__name__}: {exc}",
            "url": url,
        }
    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {"ok": False, "error": "bad_json", "detail": raw[:400], "url": url}
    if isinstance(parsed, dict):
        if "ok" not in parsed:
            parsed = {**parsed, "ok": True}
        return parsed
    return {"ok": True, "data": parsed}


def hub_board(project_id: str) -> dict[str, Any]:
    pid = urllib.parse.quote((project_id or "").strip())
    return _request("GET", f"{hub_base()}/api/desktop/lens/{pid}/board")


def hub_git(project_id: str) -> dict[str, Any]:
    pid = urllib.parse.quote((project_id or "").strip())
    return _request("GET", f"{hub_base()}/api/desktop/lens/{pid}/git/summary")


def hub_locate(
    project_id: str,
    query: str,
    *,
    glob: str = "",
    limit: int = 12,
) -> dict[str, Any]:
    pid = urllib.parse.quote((project_id or "").strip())
    q = urllib.parse.urlencode(
        {"q": query, "glob": glob or "", "limit": int(limit or 12)}
    )
    return _request("GET", f"{hub_base()}/api/desktop/lens/{pid}/locate?{q}")


def hub_file(project_id: str, path: str) -> dict[str, Any]:
    pid = urllib.parse.quote((project_id or "").strip())
    q = urllib.parse.urlencode({"path": path})
    return _request("GET", f"{hub_base()}/api/desktop/lens/{pid}/file?{q}")


def hub_grep(
    project_id: str,
    query: str,
    *,
    glob: str = "",
) -> dict[str, Any]:
    pid = urllib.parse.quote((project_id or "").strip())
    q = urllib.parse.urlencode({"q": query, "glob": glob or ""})
    return _request("GET", f"{hub_base()}/api/desktop/lens/{pid}/grep?{q}")


def hub_repair(
    project_id: str,
    action: str = "clear_blockers",
    *,
    task_id: str = "",
    epic_id: str = "",
    to_col: str = "planned",
    reason: str = "desktop_agent_hub_tool",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": (project_id or "").strip(),
        "action": (action or "clear_blockers").strip().lower() or "clear_blockers",
        "reason": reason,
        "source": "hub_agent_tools",
        "to_col": to_col or "planned",
    }
    if (task_id or "").strip():
        body["task_id"] = task_id.strip()
    if (epic_id or "").strip():
        body["epic_id"] = epic_id.strip()
    return _request(
        "POST",
        f"{hub_base()}/api/desktop/board-repair",
        body=body,
        timeout=45.0,
    )


def hub_mind_get(project_id: str) -> dict[str, Any]:
    pid = urllib.parse.quote((project_id or "").strip())
    return _request("GET", f"{hub_base()}/api/desktop/mind/{pid}/digest")


def hub_mind_put(
    project_id: str,
    patch: dict[str, Any],
    *,
    updated_by: str = "desktop-agent",
) -> dict[str, Any]:
    pid = urllib.parse.quote((project_id or "").strip())
    body = dict(patch or {})
    body["updated_by"] = updated_by or "desktop-agent"
    return _request(
        "PUT",
        f"{hub_base()}/api/desktop/mind/{pid}/decided",
        body=body,
        timeout=20.0,
    )


def mcp_server_config(*, python_bin: str | None = None) -> dict[str, Any]:
    """ClaudeAgentOptions mcp_servers entry for ccc-hub."""
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[2]
    cmd = python_bin or sys.executable
    env = {
        "CCC_HUB_URL": hub_base(),
    }
    for key in ("CCC_HUB_AUTH", "CCC_CHAT_USER", "CCC_CHAT_PASS"):
        val = (os.environ.get(key) or "").strip()
        if val:
            env[key] = val
    return {
        "type": "stdio",
        "command": cmd,
        "args": [str(scripts / "ccc-hub-agent-mcp.py")],
        "env": env,
    }

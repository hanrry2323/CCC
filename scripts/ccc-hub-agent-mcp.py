#!/usr/bin/env python3
"""ccc-hub-agent-mcp — Desktop Agent 一等 Hub 工具（stdio MCP）。

Tools: hub_board | hub_git | hub_locate | hub_file | hub_grep | hub_repair |
       hub_mind_get | hub_mind_put

结果仅供 Agent 内化；禁止把 CLI / outbox 路径贴进用户正文。
契约：docs/product/loop-engineer-authority.md · Desktop 板务 · Agent 本职
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(SCRIPTS / "chat_server") not in sys.path:
    sys.path.insert(0, str(SCRIPTS / "chat_server"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from chat_server.services import hub_agent_tools as hat  # noqa: E402

mcp = FastMCP(
    "ccc-hub",
    instructions=(
        "CCC Hub lens / board-repair / L1 mind for Desktop App Agent. "
        "For ops (project ccc): hub_board → hub_repair(status) → clear_blockers when "
        "abnormal/failed/stuck_running_epics; never tell user to re-dispatch in business chat. "
        "Never tell the user to run Terminal or write transfer-outbox. "
        "Internalize tool results; reply in short human Chinese with board numbers."
    ),
)


def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)[:12000]


@mcp.tool()
def hub_board(project_id: str) -> str:
    """Live board counts + inflight for a registered project. Call before product talk."""
    return _dump(hat.hub_board(project_id))


@mcp.tool()
def hub_git(project_id: str) -> str:
    """Git summary (branch/dirty/recent) via Hub lens — not local business tree."""
    return _dump(hat.hub_git(project_id))


@mcp.tool()
def hub_locate(project_id: str, query: str, glob: str = "", limit: int = 12) -> str:
    """Locate files by symbol/keyword on the 2017 authoritative workspace."""
    return _dump(hat.hub_locate(project_id, query, glob=glob, limit=limit))


@mcp.tool()
def hub_file(project_id: str, path: str) -> str:
    """Read one relative file from the authoritative workspace via Hub lens."""
    return _dump(hat.hub_file(project_id, path))


@mcp.tool()
def hub_grep(project_id: str, query: str, glob: str = "") -> str:
    """Grep authoritative workspace via Hub lens."""
    return _dump(hat.hub_grep(project_id, query, glob=glob))


@mcp.tool()
def hub_repair(
    project_id: str,
    action: str = "clear_blockers",
    task_id: str = "",
    epic_id: str = "",
    to_col: str = "planned",
    reason: str = "desktop_agent_hub_tool",
) -> str:
    """Board stewardship (Agent duty). Actions: status|archive|hide_done|reopen|purge_flow|clear_blockers.

    status/clear_blockers also cover stuck_running_epics (running with missing/no-inflight kids).
    When abnormal/failed/ghost/orphan-running block progress: call clear_blockers — do not bounce user.
    Do NOT ask the user to paste outbox/Terminal commands. Do NOT file hygiene epics.
    """
    return _dump(
        hat.hub_repair(
            project_id,
            action,
            task_id=task_id,
            epic_id=epic_id,
            to_col=to_col,
            reason=reason,
        )
    )


@mcp.tool()
def hub_mind_get(project_id: str) -> str:
    """Fetch L1 project mind digest (observed + decided)."""
    return _dump(hat.hub_mind_get(project_id))


@mcp.tool()
def hub_mind_put(
    project_id: str,
    goals_json: str = "",
    constraints_json: str = "",
    open_questions_json: str = "",
    architecture_choices_json: str = "",
) -> str:
    """Merge L1b decided mind. Pass JSON arrays as strings for fields you want to replace.

    Example goals_json: '[{\"text\":\"paper probe\",\"exit_condition\":\"DRY_RUN=true …\",\"status\":\"planned\"}]'
    Forbidden: invent / enable Engine / backlog cards.
    """
    patch: dict[str, Any] = {}
    for key, raw in (
        ("goals", goals_json),
        ("constraints", constraints_json),
        ("open_questions", open_questions_json),
        ("architecture_choices", architecture_choices_json),
    ):
        s = (raw or "").strip()
        if not s:
            continue
        try:
            patch[key] = json.loads(s)
        except json.JSONDecodeError:
            return _dump({"ok": False, "error": f"invalid_json_{key}"})
    if not patch:
        return _dump({"ok": False, "error": "empty_patch"})
    return _dump(hat.hub_mind_put(project_id, patch))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

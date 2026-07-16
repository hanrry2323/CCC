"""Chat ↔ CCC Board proxy — create/move/status + optional plan/phases seed."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from ..auth import check_auth
from ..services.board_client import board_proxy
from .projects import PROJECTS, PROJECT_TO_WORKSPACE, reload_projects

router = APIRouter()


def _resolve_workspace(body: dict | None, request: Request) -> str:
    body = body or {}
    ws = (
        body.get("workspace")
        or request.query_params.get("workspace")
        or "CCC"
    )
    return str(ws).strip() or "CCC"


def _workspace_root(workspace: str) -> Path | None:
    """Map board workspace id → filesystem root."""
    if not PROJECTS:
        reload_projects()
    for pid, ws in PROJECT_TO_WORKSPACE.items():
        if ws == workspace and pid in PROJECTS:
            return Path(PROJECTS[pid]["path"])
    # Fallback: case-insensitive match on project id
    key = workspace.lower().replace(" ", "-")
    if key in PROJECTS:
        return Path(PROJECTS[key]["path"])
    return None


def _write_seed_artifacts(
    workspace: str,
    task_id: str,
    plan_md: str | None,
    phases_jsonl: str | None,
) -> dict:
    """Write optional plan/phases so Engine can skip product and go planned→dev."""
    written = {}
    if not plan_md and not phases_jsonl:
        return written
    root = _workspace_root(workspace)
    if root is None:
        raise HTTPException(
            status_code=400,
            detail=f"cannot resolve workspace path for seed artifacts: {workspace}",
        )
    if plan_md:
        plans = root / ".ccc" / "plans"
        plans.mkdir(parents=True, exist_ok=True)
        path = plans / f"{task_id}.plan.md"
        path.write_text(plan_md, encoding="utf-8")
        written["plan"] = str(path)
    if phases_jsonl:
        phases = root / ".ccc" / "phases"
        phases.mkdir(parents=True, exist_ok=True)
        path = phases / f"{task_id}.phases.json"
        path.write_text(phases_jsonl.rstrip() + "\n", encoding="utf-8")
        written["phases"] = str(path)
    return written


@router.get("/api/board/proxy/board")
async def board_proxy_board(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy("GET", "/api/board", params={"workspace": workspace})


@router.get("/api/board/proxy/dashboard")
async def board_proxy_dashboard(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy("GET", "/api/dashboard", params={"workspace": workspace})


@router.get("/api/board/proxy/roles")
async def board_proxy_roles(request: Request):
    check_auth(request)
    return await board_proxy("GET", "/api/roles")


@router.get("/api/board/proxy/timeline")
async def board_proxy_timeline(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy("GET", "/api/timeline", params={"workspace": workspace})


@router.get("/api/board/proxy/tasks/{task_id}")
async def board_proxy_get_task(request: Request, task_id: str, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy(
        "GET", f"/api/tasks/{task_id}", params={"workspace": workspace}
    )


@router.get("/api/board/proxy/tasks/{task_id}/events")
async def board_proxy_task_events(request: Request, task_id: str, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy(
        "GET", f"/api/tasks/{task_id}/events", params={"workspace": workspace}
    )


@router.post("/api/board/proxy/tasks")
async def board_proxy_create_task(request: Request):
    """Create backlog task; optional plan_md + phases_jsonl skip product."""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    workspace = _resolve_workspace(body, request)
    body["workspace"] = workspace

    plan_md = body.pop("plan_md", None)
    phases_jsonl = body.pop("phases_jsonl", None)
    if plan_md is not None and not isinstance(plan_md, str):
        raise HTTPException(status_code=400, detail="plan_md must be string")
    if phases_jsonl is not None and not isinstance(phases_jsonl, str):
        raise HTTPException(status_code=400, detail="phases_jsonl must be string")

    resp = await board_proxy("POST", "/api/tasks", json_body=body)

    # Attach seed artifacts only on successful create
    if resp.status_code in (200, 201) and (plan_md or phases_jsonl):
        try:
            import json

            payload = json.loads(resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else resp.body)
        except Exception:
            payload = {}
        tid = payload.get("task_id") or body.get("id")
        if tid:
            try:
                written = _write_seed_artifacts(workspace, tid, plan_md, phases_jsonl)
                payload["seeded"] = written
                payload["skip_product"] = bool(written.get("plan") and written.get("phases"))
                return JSONResponse(content=payload, status_code=resp.status_code)
            except HTTPException:
                raise
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"seed artifacts failed: {exc}") from exc
    return resp


@router.post("/api/board/proxy/tasks/move")
async def board_proxy_move_task(request: Request):
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    body["workspace"] = _resolve_workspace(body, request)
    return await board_proxy("POST", "/api/tasks/move", json_body=body)

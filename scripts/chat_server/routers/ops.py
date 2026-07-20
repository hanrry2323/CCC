"""Hub Ops API — /api/ops/* 只读探针 + 受控日审/建卡。"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..auth import check_auth
from .projects import PROJECTS, PROJECT_TO_WORKSPACE, reload_projects

router = APIRouter()

SCRIPTS = Path(__file__).resolve().parents[2]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _workspaces() -> dict[str, str]:
    reload_projects()
    out: dict[str, str] = {}
    for pid, info in PROJECTS.items():
        ws = PROJECT_TO_WORKSPACE.get(pid, pid)
        path = (info or {}).get("path")
        if path:
            out[ws] = path
    if "CCC" not in out:
        out["CCC"] = str(SCRIPTS.parent)
    return out


def _ws_path(workspace: str) -> Path:
    spaces = _workspaces()
    if workspace in spaces:
        return Path(spaces[workspace]).expanduser()
    # try project id
    reload_projects()
    for pid, info in PROJECTS.items():
        if pid == workspace.lower() or PROJECT_TO_WORKSPACE.get(pid) == workspace:
            return Path(info["path"]).expanduser()
    raise HTTPException(status_code=400, detail=f"unknown workspace: {workspace}")


@router.get("/api/ops/overview")
async def ops_overview(request: Request):
    check_auth(request)
    from _ops_probe import overview

    return overview()


@router.get("/api/ops/ports")
async def ops_ports(request: Request, refresh: int = 0):
    check_auth(request)
    from _ops_probe import probe_ports

    return probe_ports(use_cache=not bool(refresh))


@router.get("/api/ops/resources")
async def ops_resources(request: Request):
    check_auth(request)
    from _ops_probe import local_resources

    return local_resources()


@router.get("/api/ops/workspaces")
async def ops_workspaces(request: Request):
    check_auth(request)
    from _ops_probe import workspace_summaries

    return {
        "workspaces": workspace_summaries(_workspaces()),
    }


@router.get("/api/ops/daily-review")
async def ops_daily_review(request: Request):
    check_auth(request)
    from _ops_probe import list_daily_reviews

    return list_daily_reviews(_workspaces())


class DailyReviewRunBody(BaseModel):
    workspace: str = "CCC"
    apply: bool = False


@router.post("/api/ops/daily-review/run")
async def ops_daily_review_run(request: Request, body: DailyReviewRunBody):
    check_auth(request)
    from _ops_probe import run_daily_review

    path = _ws_path(body.workspace)
    result = run_daily_review(path, apply=bool(body.apply))
    if result.get("error") == "debounced":
        raise HTTPException(status_code=429, detail=result)
    return result


@router.get("/api/ops/kb-health")
async def ops_kb_health(request: Request):
    check_auth(request)
    from _ops_probe import kb_health

    return kb_health()


@router.get("/api/ops/risks")
async def ops_risks(request: Request):
    check_auth(request)
    try:
        from _ops_probe import collect_risks

        board_abnormal: list = []
        engine_running = None
        control_mode = None
        try:
            from _ccc_control import get_mode
            from _engine_wake import is_engine_running

            control_mode = get_mode()
            engine_running = is_engine_running()
        except Exception:
            pass

        try:
            from _board_store import FileBoardStore

            for ws_id, path in _workspaces().items():
                root = Path(path).expanduser()
                if not root.is_dir():
                    continue
                store = FileBoardStore(root)
                for t in store.list_tasks("abnormal"):
                    t = dict(t)
                    t["workspace"] = ws_id
                    board_abnormal.append(t)
        except Exception:
            pass

        return collect_risks(
            _workspaces(),
            board_abnormal=board_abnormal,
            engine_running=engine_running,
            control_mode=control_mode,
        )
    except Exception as e:
        return {
            "count": 1,
            "high": 0,
            "risks": [
                {
                    "id": "risks-error",
                    "severity": "medium",
                    "source": "ops",
                    "title": "风险聚合暂时失败",
                    "detail": str(e)[:300],
                }
            ],
            "error": str(e),
        }


@router.get("/api/ops/ops-auto")
async def ops_auto_queue(request: Request):
    check_auth(request)
    from _ops_probe import list_ops_auto_tasks

    return {"tasks": list_ops_auto_tasks(_workspaces())}


@router.get("/api/ops/deploy")
async def ops_deploy(request: Request):
    check_auth(request)
    from _ops_probe import deploy_targets

    return deploy_targets()


@router.get("/api/ops/docs-debt")
async def ops_docs_debt(request: Request):
    check_auth(request)
    from _ops_probe import docs_debt_scan

    return docs_debt_scan(_workspaces())


@router.get("/api/ops/quality")
async def ops_quality(request: Request):
    check_auth(request)
    from _ops_probe import quality_summary

    return quality_summary(_workspaces())


@router.get("/api/ops/router-usage")
async def ops_router_usage(request: Request, refresh: int = 0):
    """兼容残留：ai-loop-router 已退役，返回零值 stub。"""
    check_auth(request)
    _ = refresh
    from _ops_probe import fetch_router_usage

    return fetch_router_usage(use_cache=False)


@router.get("/api/ops/summary")
async def ops_summary(request: Request):
    """Phase 3.2: 聚合端点 — 单次返回 ops 页所需全部只读探针，替代前端 11 次 GET。"""
    check_auth(request)
    import asyncio

    from _ops_probe import (
        overview,
        probe_ports,
        local_resources,
        workspace_summaries,
        list_daily_reviews,
        kb_health,
        deploy_targets,
        docs_debt_scan,
        list_ops_auto_tasks,
        quality_summary,
    )

    async def _run(func, *args):
        return await asyncio.to_thread(func, *args)

    spaces = _workspaces()
    # risks 端点有自定义聚合逻辑（board_abnormal + engine_running），直接复用其 handler
    try:
        risks_result = await ops_risks(request)
    except Exception as exc:
        risks_result = {"error": str(exc)[:120]}

    try:
        results = await asyncio.gather(
            _run(overview),
            _run(probe_ports, True),
            _run(local_resources),
            _run(workspace_summaries, spaces),
            _run(list_daily_reviews, spaces),
            _run(kb_health),
            _run(deploy_targets),
            _run(docs_debt_scan, spaces),
            _run(list_ops_auto_tasks, spaces),
            _run(quality_summary, spaces),
            return_exceptions=True,
        )
    except Exception as exc:
        return {"error": str(exc)[:200]}

    keys = [
        "overview",
        "ports",
        "resources",
        "workspaces",
        "daily",
        "kb",
        "deploy",
        "docs",
        "auto",
        "quality",
    ]
    out: dict = {"risks": risks_result}
    for k, r in zip(keys, results):
        out[k] = r if not isinstance(r, Exception) else {"error": str(r)[:120]}
    return out


class AdoptBody(BaseModel):
    workspace: str = "CCC"
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = Field(default_factory=list)


@router.post("/api/ops/adopt")
async def ops_adopt(request: Request, body: AdoptBody):
    """一键采纳建议 → backlog（tags 含 ops-auto）。不是 invent。"""
    check_auth(request)
    from _ops_probe import adopt_suggestion

    path = _ws_path(body.workspace)
    result = adopt_suggestion(
        path,
        title=body.title.strip(),
        description=body.description or "",
        tags=list(body.tags or []),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

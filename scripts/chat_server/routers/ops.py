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


@router.get("/api/ops/resources/history")
async def ops_resources_history(request: Request, n: int = 120):
    """Mac2017 CPU/内存曲线 + 并行容量建议（Engine 每 ~60s 埋点）。"""
    check_auth(request)
    from _ops_probe import host_resources_history

    n = max(12, min(int(n or 120), 720))
    return host_resources_history(n)


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
    workspace: str = Field(default="", description="engine-eligible app id or path")
    apply: bool = False
    all_apps: bool = False


@router.post("/api/ops/daily-review/run")
async def ops_daily_review_run(request: Request, body: DailyReviewRunBody):
    check_auth(request)
    from _ops_probe import resolve_ammo_workspace, run_daily_review

    if body.all_apps:
        result = run_daily_review(Path("."), apply=bool(body.apply), all_apps=True)
        if result.get("error") == "debounced":
            raise HTTPException(status_code=429, detail=result)
        return result

    if not (body.workspace or "").strip():
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "workspace required unless all_apps=true",
                "code": "ops-ammo-workspace-required",
            },
        )

    resolved = resolve_ammo_workspace(body.workspace)
    if not resolved.get("ok"):
        raise HTTPException(status_code=400, detail=resolved)
    result = run_daily_review(Path(resolved["path"]), apply=bool(body.apply))
    if result.get("error") == "debounced":
        raise HTTPException(status_code=429, detail=result)
    result["workspace"] = resolved.get("workspace")
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
        host_resources_history,
        workspace_summaries,
        list_daily_reviews,
        kb_health,
        deploy_targets,
        docs_debt_scan,
        list_ops_auto_tasks,
        quality_summary,
        logistics_heartbeat,
        control_runtime_snapshot,
        recent_failures_fleet,
        abnormal_cards_fleet,
        ready_to_dispatch,
        ops_health_envelope,
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
            _run(host_resources_history, 90),
            _run(workspace_summaries, spaces),
            _run(list_daily_reviews, spaces),
            _run(kb_health),
            _run(deploy_targets),
            _run(docs_debt_scan, spaces),
            _run(list_ops_auto_tasks, spaces),
            _run(quality_summary, spaces),
            _run(logistics_heartbeat, spaces),
            _run(control_runtime_snapshot),
            _run(recent_failures_fleet, spaces),
            _run(abnormal_cards_fleet, spaces),
            return_exceptions=True,
        )
    except Exception as exc:
        return {"error": str(exc)[:200]}

    keys = [
        "overview",
        "ports",
        "resources",
        "resources_history",
        "workspaces",
        "daily",
        "kb",
        "deploy",
        "docs",
        "auto",
        "quality",
        "logistics",
        "control",
        "recent_failures",
        "abnormal_cards",
    ]
    out: dict = {"risks": risks_result}
    for k, r in zip(keys, results):
        out[k] = r if not isinstance(r, Exception) else {"error": str(r)[:120]}

    # Desktop expects {workspaces: [...]}; SPA table uses .workspaces too
    ws_raw = out.get("workspaces")
    if isinstance(ws_raw, list):
        out["workspaces"] = {"workspaces": ws_raw}
    elif isinstance(ws_raw, dict) and "error" in ws_raw:
        out["workspaces"] = {"workspaces": [], "error": ws_raw.get("error")}

    # failures / abnormal always list for Desktop decode
    for list_key in ("recent_failures", "abnormal_cards"):
        raw = out.get(list_key)
        if isinstance(raw, Exception) or (isinstance(raw, dict) and "error" in raw):
            out[list_key] = []
        elif not isinstance(raw, list):
            out[list_key] = []

    ctrl = out.get("control") if isinstance(out.get("control"), dict) else {}
    ws_list = (out.get("workspaces") or {}).get("workspaces") or []
    hist = out.get("resources_history") if isinstance(out.get("resources_history"), dict) else {}
    try:
        out["ready_to_dispatch"] = ready_to_dispatch(
            control=ctrl,
            risks=risks_result if isinstance(risks_result, dict) else {},
            workspaces=ws_list if isinstance(ws_list, list) else [],
            resources_history=hist,
        )
    except Exception as exc:
        out["ready_to_dispatch"] = {
            "ok": False,
            "reason": f"ready 合成失败: {exc}"[:160],
            "blockers": ["ready_compose_error"],
        }

    try:
        env = ops_health_envelope(
            control=ctrl,
            risks=risks_result if isinstance(risks_result, dict) else {},
            ready=out.get("ready_to_dispatch")
            if isinstance(out.get("ready_to_dispatch"), dict)
            else {},
            logistics=out.get("logistics") if isinstance(out.get("logistics"), dict) else {},
            resources_history=hist,
            ports=out.get("ports") if isinstance(out.get("ports"), dict) else {},
            overview=out.get("overview") if isinstance(out.get("overview"), dict) else {},
        )
        out["severity"] = env.get("severity") or "amber"
        out["human_line"] = env.get("human_line") or ""
        out["alerts"] = env.get("alerts") or []
        out["amber_notes"] = env.get("amber_notes") or []
        out["domains"] = env.get("domains") or {}
        out["health"] = env  # full envelope for SPA / debug
    except Exception as exc:
        out["severity"] = "red"
        out["human_line"] = f"健康合成失败：{exc}"[:120]
        out["alerts"] = [
            {
                "id": "health-compose-error",
                "title": "运维健康合成失败",
                "detail": str(exc)[:200],
                "source": "ops",
                "severity": "red",
                "copy_payload": (
                    "【CCC 运维红灯】健康合成失败\n"
                    f"详情：{exc}\n"
                    "建议：查 Hub 日志与 scripts/_ops_probe.ops_health_envelope"
                ),
            }
        ]
        out["amber_notes"] = []
        out["domains"] = {}

    # fold control into logistics for older Desktop clients
    if isinstance(out.get("logistics"), dict) and isinstance(ctrl, dict):
        out["logistics"]["control"] = ctrl
        out["logistics"]["engine_running"] = ctrl.get("engine_running")
        out["logistics"]["mode"] = ctrl.get("mode")

    # P3：项目心智 L1 只读一览（不阻塞主路径）
    try:
        from chat_server.services import agent_mind
        from .projects import PROJECTS, get_project_path

        minds: list[dict] = []
        for pid, info in list((PROJECTS or {}).items())[:12]:
            pid = str(pid or "").strip()
            if not pid or pid == "ccc":
                continue
            if (info or {}).get("role") == "orch" or (info or {}).get("is_orch"):
                continue
            path = get_project_path(pid)
            if not path:
                continue
            try:
                dig = agent_mind.build_digest(
                    Path(path), project_id=pid, use_cache=True, persist=False
                )
                minds.append(
                    {
                        "project_id": pid,
                        "as_of": dig.get("as_of"),
                        "board_summary": (dig.get("observed") or {}).get("board_summary"),
                        "daily": (dig.get("observed") or {}).get("daily_review_headline"),
                        "weekly": (dig.get("observed") or {}).get("weekly_review_headline"),
                        "constraints_n": len((dig.get("decided") or {}).get("constraints") or []),
                    }
                )
            except Exception as exc:
                minds.append({"project_id": pid, "error": str(exc)[:80]})
        out["agent_minds"] = {"ok": True, "items": minds}
    except Exception as exc:
        out["agent_minds"] = {"ok": False, "error": str(exc)[:120]}
    return out


class AdoptBody(BaseModel):
    workspace: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = Field(default_factory=list)


@router.post("/api/ops/adopt")
async def ops_adopt(request: Request, body: AdoptBody):
    """一键采纳建议 → backlog（tags 含 ops-auto）。不是 invent。仅 engine-eligible 业务仓。"""
    check_auth(request)
    from _ops_probe import adopt_suggestion, resolve_ammo_workspace

    resolved = resolve_ammo_workspace(body.workspace)
    if not resolved.get("ok"):
        raise HTTPException(status_code=400, detail=resolved)
    result = adopt_suggestion(
        Path(resolved["path"]),
        title=body.title.strip(),
        description=body.description or "",
        tags=list(body.tags or []),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

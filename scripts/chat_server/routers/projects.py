import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..auth import check_auth
from .. import config

router = APIRouter()

PROJECTS: dict[str, dict] = {}
PROJECT_TO_WORKSPACE: dict[str, str] = {}
# Board 同步拉取会堵死 uvicorn 事件循环；TTL 缓存 + 线程池卸载是根治
_PROJECTS_CACHE_TTL_S = 20.0
_projects_loaded_at = 0.0
_reload_lock = asyncio.Lock()


def _board_fetch_projects() -> tuple[dict[str, dict], dict[str, str]]:
    """同步拉取 Board workspace → projects（必须在线程池里跑）。"""
    new_projects: dict[str, dict] = {}
    new_mapping: dict[str, str] = {}
    try:
        import httpx
        import sys
        from pathlib import Path

        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from _workspace_registry import (
            entry_engine_eligible,
            is_orch_path,
            list_registered_entries,
        )

        # 短超时：Board 慢时立刻 fallback，别拖死 Hub
        resp = httpx.get(f"{config.BOARD_URL}/api/board", timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            workspaces = data.get("workspaces", {})
            reg_by_path = {e["path"]: e for e in list_registered_entries()}
            for ws_id, ws_path in workspaces.items():
                if ws_id.startswith("."):
                    continue
                # Display: orch gets a clear label; apps use registry/workspace id
                name = "CCC（编排）" if ws_id.upper() == "CCC" else ws_id
                pid = ws_id.lower().replace(" ", "-")
                try:
                    resolved = str(Path(ws_path).expanduser().resolve())
                except OSError:
                    resolved = str(ws_path)
                reg_entry = reg_by_path.get(resolved)
                role = "orch" if is_orch_path(resolved) else "app"
                if reg_entry:
                    role = reg_entry.get("role") or role
                    engine_ok = entry_engine_eligible(reg_entry)
                elif is_orch_path(resolved):
                    # Unregistered orch home still non-dispatchable
                    engine_ok = False
                    role = "orch"
                else:
                    # Board-visible but not in Engine registry → Hub may chat, not dispatch
                    engine_ok = False
                new_projects[pid] = {
                    "name": name,
                    "path": ws_path,
                    "role": role,
                    "engine_eligible": engine_ok,
                }
                new_mapping[pid] = ws_id
    except Exception as exc:
        import logging
        logging.getLogger("ccc-chat").warning("Board unreachable: %s", exc)

    if not new_projects:
        new_projects.update(config._PROJECTS_FALLBACK)
        # Annotate fallback
        for pid, info in list(new_projects.items()):
            if not isinstance(info, dict):
                continue
            info = dict(info)
            if pid == "ccc" or str(info.get("name", "")).upper() == "CCC":
                info["role"] = "orch"
                info["engine_eligible"] = False
            else:
                info.setdefault("role", "app")
                info.setdefault("engine_eligible", True)
            new_projects[pid] = info

    return new_projects, new_mapping


def reload_projects(*, force: bool = False) -> None:
    """同步入口（启动 / 线程内）。带 TTL，避免每次 API 都打 Board。"""
    global PROJECTS, PROJECT_TO_WORKSPACE, _projects_loaded_at
    now = time.monotonic()
    if (
        not force
        and PROJECTS
        and (now - _projects_loaded_at) < _PROJECTS_CACHE_TTL_S
    ):
        return
    new_projects, new_mapping = _board_fetch_projects()
    PROJECTS.clear()
    PROJECTS.update(new_projects)
    PROJECT_TO_WORKSPACE.clear()
    PROJECT_TO_WORKSPACE.update(new_mapping)
    _projects_loaded_at = time.monotonic()


async def reload_projects_async(*, force: bool = False) -> None:
    """异步安全：Board HTTP 放到线程池，不堵事件循环。"""
    global PROJECTS, PROJECT_TO_WORKSPACE, _projects_loaded_at
    now = time.monotonic()
    if (
        not force
        and PROJECTS
        and (now - _projects_loaded_at) < _PROJECTS_CACHE_TTL_S
    ):
        return
    async with _reload_lock:
        now = time.monotonic()
        if (
            not force
            and PROJECTS
            and (now - _projects_loaded_at) < _PROJECTS_CACHE_TTL_S
        ):
            return
        new_projects, new_mapping = await asyncio.to_thread(_board_fetch_projects)
        PROJECTS.clear()
        PROJECTS.update(new_projects)
        PROJECT_TO_WORKSPACE.clear()
        PROJECT_TO_WORKSPACE.update(new_mapping)
        _projects_loaded_at = time.monotonic()


reload_projects(force=True)


def get_project_path(project_id: str) -> str:
    # 允许迟到登记的 workspace（如新建 clawmed-ccc）
    if project_id not in PROJECTS:
        reload_projects(force=True)
    proj = PROJECTS.get(project_id)
    if not proj:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"unknown project: {project_id}")
    return proj["path"]


def default_project_id() -> str | None:
    """Prefer sticky/env app; never prefer orch when apps exist.

    Order: CCC_HUB_DEFAULT_PROJECT → ~/.ccc/hub-prefs.json last_project
    → first engine-eligible app.
    """
    import json
    import os
    from pathlib import Path

    # 用已缓存 PROJECTS，禁止再同步打 Board（曾导致每次 list 双倍阻塞）
    apps = [
        pid
        for pid, info in PROJECTS.items()
        if info.get("engine_eligible", True) and info.get("role") != "orch"
    ]
    if not apps:
        return next(iter(PROJECTS), None)

    candidates: list[str] = []
    env = (os.environ.get("CCC_HUB_DEFAULT_PROJECT") or "").strip().lower()
    if env:
        candidates.append(env)
    prefs = Path.home() / ".ccc" / "hub-prefs.json"
    if prefs.is_file():
        try:
            data = json.loads(prefs.read_text(encoding="utf-8"))
            last = str(data.get("last_project") or "").strip().lower()
            if last:
                candidates.append(last)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    for cand in candidates:
        if cand in apps:
            return cand
    return apps[0]


@router.get("/api/projects")
async def list_projects(request: Request):
    check_auth(request)
    # TTL 缓存 + 线程池：新建 workspace 最多 20s 可见，但 Hub 不再被 Board 拖死
    await reload_projects_async()
    default_id = default_project_id()
    return {
        "projects": [
            {
                "id": pid,
                "name": info["name"],
                "path": info["path"],
                "workspace": PROJECT_TO_WORKSPACE.get(pid, pid),
                "role": info.get("role") or "app",
                "engine_eligible": bool(info.get("engine_eligible", True)),
            }
            for pid, info in PROJECTS.items()
        ],
        "default_project": default_id,
    }


@router.get("/api/projects/{project_id}/baseline")
async def project_baseline(project_id: str, request: Request):
    """结构化项目对齐基线（程序侧，不调 LLM）。"""
    check_auth(request)
    path = get_project_path(project_id)
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[2]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _project_baseline import baseline_prompt_for_claude, collect_baseline

    baseline = collect_baseline(Path(path), project_id=project_id)
    return {
        "ok": True,
        "baseline": baseline,
        "prompt": baseline_prompt_for_claude(baseline),
    }


@router.get("/api/skills")
async def list_skills(
    request: Request,
    project: str | None = None,
    include_engine: bool = False,
):
    """扫描本机/项目 Skill 目录，供转任务卡 chips 使用（软偏好）。

    默认隐藏 Engine 角色 skill（ccc-product 等）；include_engine=1 可显示。
    """
    check_auth(request)
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[2]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _skills_catalog import discover_skills

    project_path = None
    if project:
        try:
            project_path = get_project_path(project)
        except Exception:
            project_path = None
    skills = discover_skills(
        project_path=project_path,
        ccc_home=scripts.parent,
        include_engine=include_engine,
    )
    return {
        "ok": True,
        "skills": skills,
        "count": len(skills),
        "include_engine": include_engine,
    }


@router.get("/api/hub-config")
async def hub_config(request: Request):
    """Hub 客户端配置（Remote Desktop Shell + 并发上限）。"""
    check_auth(request)
    import json
    import os
    from pathlib import Path

    from .. import config as hub_config_mod

    workspace_map: dict = {}
    raw_map = (os.environ.get("CCC_DESKTOP_WORKSPACE_MAP") or "").strip()
    if raw_map:
        try:
            parsed = json.loads(raw_map)
            if isinstance(parsed, dict):
                workspace_map = {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            pass
    map_file = Path.home() / ".ccc" / "desktop-workspace-map.json"
    if map_file.is_file():
        try:
            data = json.loads(map_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                workspace_map = {**workspace_map, **{str(k): str(v) for k, v in data.items()}}
        except (json.JSONDecodeError, OSError):
            pass

    agent_url = (
        os.environ.get("CCC_DESKTOP_AGENT_URL")
        or os.environ.get("CCC_AGENT_URL")
        or "http://192.168.3.140:7788"
    )
    return {
        "ok": True,
        "chat_session_max_live": hub_config_mod.CHAT_SESSION_MAX_LIVE,
        "chat_session_idle_ttl": hub_config_mod.CHAT_SESSION_IDLE_TTL,
        "desktop_remote": True,
        "agent_proxy": "/api/agent",
        "desktop_agent_url": agent_url,
        "workspace_map": workspace_map,
    }

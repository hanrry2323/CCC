from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..auth import check_auth
from .. import config

router = APIRouter()

PROJECTS: dict[str, dict] = {}
PROJECT_TO_WORKSPACE: dict[str, str] = {}


def reload_projects():
    global PROJECTS, PROJECT_TO_WORKSPACE
    new_projects = {}
    new_mapping = {}
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
            lookup_entry,
        )

        resp = httpx.get(f"{config.BOARD_URL}/api/board", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            workspaces = data.get("workspaces", {})
            name_map = {
                "CCC": "CCC（编排）",
                "qxo": "QXO Observer",
                "xianyu": "xianyu",
                "qb": "qb Dashboard",
                "qx": "qx (archived parts)",
                "clawmed-ccc": "cla (clawmed-ccc)",
            }
            reg_by_path = {e["path"]: e for e in list_registered_entries()}
            for ws_id, ws_path in workspaces.items():
                if ws_id.startswith("."):
                    continue
                name = name_map.get(ws_id, ws_id)
                pid = ws_id.lower().replace(" ", "-")
                try:
                    resolved = str(Path(ws_path).expanduser().resolve())
                except OSError:
                    resolved = str(ws_path)
                entry = reg_by_path.get(resolved) or lookup_entry(resolved)
                role = "orch" if is_orch_path(resolved) else "app"
                engine_ok = True
                if entry:
                    role = entry.get("role") or role
                    engine_ok = entry_engine_eligible(entry)
                elif is_orch_path(resolved):
                    engine_ok = False
                    role = "orch"
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

    PROJECTS.clear()
    PROJECTS.update(new_projects)
    PROJECT_TO_WORKSPACE.clear()
    PROJECT_TO_WORKSPACE.update(new_mapping)


reload_projects()


def get_project_path(project_id: str) -> str:
    # 允许迟到登记的 workspace（如新建 clawmed-ccc）
    if project_id not in PROJECTS:
        reload_projects()
    proj = PROJECTS.get(project_id)
    if not proj:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"unknown project: {project_id}")
    return proj["path"]


def default_project_id() -> str | None:
    """Prefer first engine-eligible app; never prefer orch when apps exist."""
    reload_projects()
    apps = [
        pid
        for pid, info in PROJECTS.items()
        if info.get("engine_eligible", True) and info.get("role") != "orch"
    ]
    if apps:
        return apps[0]
    return next(iter(PROJECTS), None)


@router.get("/api/projects")
async def list_projects(request: Request):
    check_auth(request)
    # 每次列表从 Board 重载，避免 Hub 启动后新建 workspace 不出现
    reload_projects()
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
    """Hub chat 客户端配置（并发上限等）。"""
    check_auth(request)
    from .. import config as hub_config_mod

    return {
        "ok": True,
        "chat_session_max_live": hub_config_mod.CHAT_SESSION_MAX_LIVE,
        "chat_session_idle_ttl": hub_config_mod.CHAT_SESSION_IDLE_TTL,
    }
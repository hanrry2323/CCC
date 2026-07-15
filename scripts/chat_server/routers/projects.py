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
        resp = httpx.get(f"{config.BOARD_URL}/api/board", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            workspaces = data.get("workspaces", {})
            name_map = {
                "CCC": "CCC", "qxo": "QXO Observer",
                "xianyu": "xianyu", "qb": "qb Dashboard", "qx": "qx",
            }
            for ws_id, ws_path in workspaces.items():
                if ws_id.startswith("."):
                    continue
                name = name_map.get(ws_id, ws_id.capitalize())
                pid = ws_id.lower().replace(" ", "-")
                new_projects[pid] = {"name": name, "path": ws_path}
                new_mapping[pid] = ws_id
    except Exception as exc:
        import logging
        logging.getLogger("ccc-chat").warning("Board unreachable: %s", exc)

    if not new_projects:
        new_projects.update(config._PROJECTS_FALLBACK)

    PROJECTS.clear()
    PROJECTS.update(new_projects)
    PROJECT_TO_WORKSPACE.clear()
    PROJECT_TO_WORKSPACE.update(new_mapping)


reload_projects()


def get_project_path(project_id: str) -> str:
    proj = PROJECTS.get(project_id)
    if not proj:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"unknown project: {project_id}")
    return proj["path"]


@router.get("/api/projects")
async def list_projects(request: Request):
    check_auth(request)
    return {
        "projects": [
            {"id": pid, "name": info["name"], "path": info["path"]}
            for pid, info in PROJECTS.items()
        ]
    }

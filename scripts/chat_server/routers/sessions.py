import uuid
from fastapi import APIRouter, Request, HTTPException

from ..auth import check_auth
from ..services import session_store as store
from ..services import claude_history
from .projects import get_project_path

router = APIRouter()


@router.get("/api/history")
async def list_sessions(
    request: Request,
    project: str = "ccc",
    source: str = "all",
    include_tests: bool = False,
):
    """List Hub and/or Claude Code sessions.

    source: all | hub | claude
    """
    check_auth(request)
    src = (source or "all").strip().lower()
    hub: list[dict] = []
    claude: list[dict] = []

    if src in ("all", "hub"):
        hub = store.list_sessions(project, include_tests=include_tests)
        for s in hub:
            s.setdefault("source", "hub")

    if src in ("all", "claude"):
        try:
            project_path = get_project_path(project)
            claude = claude_history.list_claude_sessions(project_path)
        except Exception:
            claude = []

    if src == "hub":
        sessions = hub
    elif src == "claude":
        sessions = claude
    else:
        sessions = hub + claude
        sessions.sort(key=lambda s: s.get("updated_at") or "", reverse=True)

    return {"sessions": sessions, "source": src}


@router.post("/api/history/cleanup-tests")
async def cleanup_tests(request: Request, project: str = "ccc"):
    """Quarantine pytest/e2e Hub sessions (ch*/sc*/sp*/…) into _trash."""
    check_auth(request)
    result = store.purge_test_sessions(project)
    return {"ok": True, **result}


@router.get("/api/history/{session_id}")
async def get_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)

    if session_id.startswith("claude:"):
        try:
            project_path = get_project_path(project)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        data = claude_history.load_claude_session(session_id, project_path)
        if data is None:
            raise HTTPException(status_code=404, detail="claude session not found")
        data["project"] = project
        return data

    data = store.get_session(session_id, project)
    if data is not None:
        data.setdefault("source", "hub")
        return data

    # Fallback: raw UUID may be a Claude transcript
    try:
        project_path = get_project_path(project)
        data = claude_history.load_claude_session(f"claude:{session_id}", project_path)
    except Exception:
        data = None
    if data is None:
        raise HTTPException(status_code=404)
    data["project"] = project
    return data


@router.patch("/api/history/{session_id}")
async def rename_session(request: Request, session_id: str, project: str = "ccc"):
    """Rename a Hub session title."""
    check_auth(request)
    if session_id.startswith("claude:"):
        raise HTTPException(
            status_code=400,
            detail="Claude 历史请在 Claude Code 内管理；Hub 仅只读展示",
        )
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=400, detail="title required")
    data = store.rename_session(session_id, project, title.strip())
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True, "session_id": session_id, "title": data.get("title")}


@router.delete("/api/history/{session_id}")
async def delete_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)
    if session_id.startswith("claude:"):
        raise HTTPException(
            status_code=400,
            detail="Claude 历史请在 Claude Code 内管理；Hub 仅只读展示",
        )
    store.delete_session(session_id, project)
    return {"ok": True}
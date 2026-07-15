import uuid
from fastapi import APIRouter, Request, HTTPException

from ..auth import check_auth
from ..services import session_store as store

router = APIRouter()


@router.get("/api/history")
async def list_sessions(request: Request, project: str = "ccc"):
    check_auth(request)
    return {"sessions": store.list_sessions(project)}


@router.get("/api/history/{session_id}")
async def get_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)
    data = store.get_session(session_id, project)
    if data is None:
        raise HTTPException(status_code=404)
    return data


@router.delete("/api/history/{session_id}")
async def delete_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)
    store.delete_session(session_id, project)
    return {"ok": True}

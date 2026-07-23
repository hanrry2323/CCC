"""Desktop Agent 项目心智 API — L1 digest / decided。

契约：docs/product/loop-engineer-authority.md · 双层心智
GET  digest/observed — 系统编译
PUT  decided — Agent/人提案（schema）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pathlib import Path

from ..auth import check_auth
from ..services import agent_mind
from .projects import get_project_path

router = APIRouter(prefix="/api/desktop/mind", tags=["desktop-mind"])


def _root(project_id: str) -> Path:
    root = get_project_path(project_id)
    if root is None:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    return Path(root)


@router.get("/{project_id}/digest")
async def get_mind_digest(request: Request, project_id: str) -> dict[str, Any]:
    """L1 digest + 项目脑包字段 brain / inject（sidecar 优先 inject）。"""
    check_auth(request)
    return agent_mind.build_digest(_root(project_id), project_id=project_id)


@router.get("/{project_id}/brain")
async def get_mind_brain(request: Request, project_id: str) -> dict[str, Any]:
    """项目脑包（CLAUDE+规划文+profile+decided 摘要）。ccc 返回空脑包。"""
    check_auth(request)
    from ..services import project_brain

    if project_id.strip().lower() == "ccc":
        return {
            "ok": True,
            "project_id": project_id,
            "brain": "",
            "brain_meta": {"skipped": "ops_agent"},
        }
    return project_brain.compile_brain(_root(project_id), project_id=project_id)


@router.get("/{project_id}/observed")
async def get_mind_observed(request: Request, project_id: str) -> dict[str, Any]:
    check_auth(request)
    observed = agent_mind.compile_observed(
        _root(project_id), project_id=project_id
    )
    return {"ok": True, "project_id": project_id, "observed": observed}


@router.get("/{project_id}/decided")
async def get_mind_decided(request: Request, project_id: str) -> dict[str, Any]:
    check_auth(request)
    decided = agent_mind.load_decided(_root(project_id))
    return {"ok": True, "project_id": project_id, "decided": decided}


@router.put("/{project_id}/decided")
async def put_mind_decided(request: Request, project_id: str) -> Any:
    """合并 L1b 决策脑。body: goals/constraints/open_questions/architecture_choices + updated_by。"""
    check_auth(request)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "invalid_json"}
        )
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "body_must_be_object"}
        )
    # 禁止写 L0 / 投卡字段
    for banned in ("hub_voice", "enable_engine", "invent", "backlog", "card_kind"):
        if banned in body:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "forbidden_field", "field": banned},
            )
    root = _root(project_id)
    try:
        decided = agent_mind.merge_decided(
            root,
            body,
            updated_by=str(body.get("updated_by") or "desktop-agent"),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": str(exc)[:200]}
        )
    # 刷新 digest
    digest = agent_mind.build_digest(
        root, project_id=project_id, use_cache=False, persist=True
    )
    return {
        "ok": True,
        "project_id": project_id,
        "decided": decided,
        "as_of": digest.get("as_of"),
        "digest_preview": str(digest.get("digest") or "")[:400],
    }


@router.post("/{project_id}/goals/{goal_id}/status")
async def post_goal_status(
    request: Request, project_id: str, goal_id: str
) -> Any:
    """Mark goal intent_stable / abandoned / probed (LPSN · S)."""
    check_auth(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    status = str(body.get("status") or "").strip().lower()
    try:
        decided = agent_mind.mark_goal_status(
            _root(project_id),
            goal_id,
            status,
            updated_by=str(body.get("updated_by") or "human"),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": str(exc)[:200]}
        )
    digest = agent_mind.build_digest(
        _root(project_id), project_id=project_id, use_cache=False, persist=True
    )
    return {
        "ok": True,
        "project_id": project_id,
        "decided": decided,
        "next_product_goal": digest.get("next_product_goal"),
    }

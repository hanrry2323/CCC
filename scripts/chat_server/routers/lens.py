"""Desktop Hub 只读透镜 API — 权威仓 board/tree/file/grep/locate/git。

契约：docs/product/loop-engineer-authority.md
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pathlib import Path

from ..auth import check_auth
from ..services import hub_lens
from .projects import get_project_path

router = APIRouter(prefix="/api/desktop/lens", tags=["desktop-lens"])


def _root(project_id: str) -> Path:
    root = get_project_path(project_id)
    if root is None:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    return Path(root)


@router.get("/{project_id}/board")
async def lens_board(request: Request, project_id: str) -> dict[str, Any]:
    check_auth(request)
    return hub_lens.collect_board(_root(project_id), project_id=project_id)


@router.get("/{project_id}/tree")
async def lens_tree(
    request: Request,
    project_id: str,
    path: str = Query("", description="relative path under project root"),
    depth: int = Query(3, ge=0, le=5),
) -> dict[str, Any]:
    check_auth(request)
    try:
        return hub_lens.collect_tree(
            _root(project_id), project_id=project_id, path=path, depth=depth
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{project_id}/file")
async def lens_file(
    request: Request,
    project_id: str,
    path: str = Query(..., description="relative file path"),
) -> dict[str, Any]:
    check_auth(request)
    try:
        return hub_lens.collect_file(_root(project_id), project_id=project_id, path=path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{project_id}/grep")
async def lens_grep(
    request: Request,
    project_id: str,
    q: str = Query(..., min_length=1),
    glob: str = Query(""),
) -> dict[str, Any]:
    check_auth(request)
    try:
        return hub_lens.collect_grep(
            _root(project_id), project_id=project_id, q=q, glob=glob
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{project_id}/locate")
async def lens_locate(
    request: Request,
    project_id: str,
    q: str = Query(..., min_length=1),
    glob: str = Query(""),
    limit: int = Query(12, ge=1, le=30),
) -> dict[str, Any]:
    """按符号/关键词收窄文件（扫风险定点定位）。"""
    check_auth(request)
    try:
        return hub_lens.collect_locate(
            _root(project_id),
            project_id=project_id,
            q=q,
            glob=glob,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{project_id}/git/summary")
async def lens_git_summary(request: Request, project_id: str) -> dict[str, Any]:
    check_auth(request)
    return hub_lens.collect_git_summary(_root(project_id), project_id=project_id)

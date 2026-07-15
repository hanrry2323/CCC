from fastapi import APIRouter, Request

from ..auth import check_auth
from ..services.board_client import board_proxy

router = APIRouter()


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


@router.post("/api/board/proxy/tasks")
async def board_proxy_create_task(request: Request):
    check_auth(request)
    body = await request.json()
    return await board_proxy("POST", "/api/tasks", json_body=body)


@router.post("/api/board/proxy/tasks/move")
async def board_proxy_move_task(request: Request):
    check_auth(request)
    body = await request.json()
    return await board_proxy("POST", "/api/tasks/move", json_body=body)

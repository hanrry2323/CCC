from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from . import config
from .routers import chat, sessions, files, board, projects

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
HUB_ASSET_VERSION = os.environ.get("CCC_HUB_ASSET_VERSION", "20260716h")


class NoStoreStaticMiddleware(BaseHTTPMiddleware):
    """防止浏览器把旧 Chat/Board 皮缓存成「打开还是旧代码」。"""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path or "/"
        if (
            path == "/"
            or path.endswith(".html")
            or path.endswith(".js")
            or path.endswith(".css")
            or path.endswith(".map")
        ):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="CCC Hub", docs_url=None, redoc_url=None)

    # F-SEC-04: 收紧 CORS；允许 localhost + 私网 LAN；禁止 "*" + credentials
    _cors_raw = os.environ.get(
        "CCC_CHAT_CORS_ORIGINS",
        "http://127.0.0.1:7777,http://localhost:7777,"
        "http://127.0.0.1:8084,http://localhost:8084,"
        "tauri://localhost,https://tauri.localhost",
    )
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_origin_regex=config.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(NoStoreStaticMiddleware)

    app.include_router(projects.router)
    app.include_router(chat.router)
    app.include_router(sessions.router)
    app.include_router(files.router)
    app.include_router(board.router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app

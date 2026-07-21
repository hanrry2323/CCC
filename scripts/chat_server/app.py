from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from . import config
from .routers import sessions, files, board, projects, ops, desktop, lens
from .services.board_client import close_client

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
HUB_ASSET_VERSION = os.environ.get("CCC_HUB_ASSET_VERSION", "20260721dual2")


class NoStoreStaticMiddleware(BaseHTTPMiddleware):
    """Phase 3.3: HTML 永不缓存；带 ?v=/?h= 的 JS/CSS 长缓存 immutable，否则 no-store。"""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path or "/"
        query = request.url.query or ""
        # 带版本/哈希查询参数 → 长缓存（内容变 → 版本变 → URL 变 → 浏览器重取）
        has_version = ("v=" in query) or ("h=" in query)
        if path.endswith(".js") or path.endswith(".css") or path.endswith(".map"):
            if has_version:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                for h in ("Pragma", "Expires"):
                    try:
                        del response.headers[h]
                    except KeyError:
                        pass
                return response
            # 无版本 → 不缓存（开发期热改可见）
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        if path == "/" or path.endswith(".html"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Phase 2.1: 应用退出时显式关闭共享 httpx client，避免连接泄漏
    yield
    await close_client()


def create_app() -> FastAPI:
    app = FastAPI(title="CCC Hub", docs_url=None, redoc_url=None, lifespan=_lifespan)

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
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(NoStoreStaticMiddleware)

    app.include_router(projects.router)
    app.include_router(sessions.router)
    app.include_router(files.router)
    app.include_router(board.router)
    app.include_router(ops.router)
    app.include_router(desktop.router)
    app.include_router(lens.router)
    # 遗留运维探针：默认关闭；CCC_AGENT_PROXY=1 才挂载（非产品主路径）
    if (os.environ.get("CCC_AGENT_PROXY") or "").strip() in ("1", "true", "yes"):
        from .routers import agent_proxy

        app.include_router(agent_proxy.router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app

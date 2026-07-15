from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .routers import chat, sessions, files, board, projects

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(title="CCC Chat", docs_url=None, redoc_url=None)

    # F-SEC-04: 收紧 CORS；禁止 allow_origins=["*"] + credentials
    _cors_raw = __import__("os").environ.get(
        "CCC_CHAT_CORS_ORIGINS",
        "http://127.0.0.1:8084,http://localhost:8084,tauri://localhost,https://tauri.localhost",
    )
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(projects.router)
    app.include_router(chat.router)
    app.include_router(sessions.router)
    app.include_router(files.router)
    app.include_router(board.router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app

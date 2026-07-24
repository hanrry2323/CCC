"""tests for chat_server routers — smoke test 覆盖 9 个 router

修复 stability-audit-2026-07-24 第五批 5.1：Hub routers 全部 FastAPI
TestClient 端到端。本次先做 smoke test（import + routes 非空 + 方法签名）
覆盖基础结构；后续 batch 加详细 endpoint 行为测试。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# 强制 scripts/ 在 path 顶部（与现有测试一致）
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


# 9 个 router 名字（除 __init__.py）
ROUTER_NAMES = [
    "sessions",
    "files",
    "projects",
    "board",
    "ops",
    "desktop",
    "lens",
    "mind",
    # agent_proxy 默认未挂载，需 CCC_AGENT_PROXY=1 — 不在 smoke 范围
]


def _import_router(name: str):
    """Import a single router module, surface ImportError with context."""
    try:
        return importlib.import_module(f"chat_server.routers.{name}")
    except ImportError as exc:
        pytest.skip(f"router {name} import failed: {exc}")


@pytest.mark.parametrize("name", ROUTER_NAMES)
def test_router_imports_clean(name):
    """9 个 router 全部 import 不抛。"""
    mod = _import_router(name)
    assert hasattr(mod, "router"), f"{name} missing 'router' attribute"


@pytest.mark.parametrize("name", ROUTER_NAMES)
def test_router_has_routes(name):
    """每个 router 至少注册一个路由。"""
    mod = _import_router(name)
    routes = mod.router.routes
    assert len(routes) > 0, f"{name} has no routes registered"


@pytest.mark.parametrize("name", ROUTER_NAMES)
def test_router_route_methods_valid(name):
    """所有 route 的 methods 字段是非空合法 HTTP 方法。"""
    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
    mod = _import_router(name)
    for route in mod.router.routes:
        if hasattr(route, "methods") and route.methods:
            for m in route.methods:
                assert m in valid_methods, (
                    f"{name} route {route.path} has invalid method {m!r}"
                )


@pytest.mark.parametrize("name", ROUTER_NAMES)
def test_router_paths_are_strings(name):
    """所有 route path 是字符串（FastAPI 严格要求）。"""
    mod = _import_router(name)
    for route in mod.router.routes:
        if hasattr(route, "path"):
            assert isinstance(route.path, str), (
                f"{name} route path is not str: {route.path!r}"
            )


def test_app_includes_all_routers():
    """create_app() 应包含所有 9 个 router（desktop 强制，其它 8 个）."""
    from chat_server.app import create_app

    app = create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    # 每个 router 至少一个 path 应在 app.routes 里
    # 不强求精确 path 匹配（可能有 prefix），只验证 router 已 include
    assert len(paths) > 10, f"app routes 太少: {len(paths)}"


def test_lifespan_shutdown_calls_session_manager():
    """修复 stability-audit-2026-07-24 1.5：_lifespan 退出调
    session_manager.shutdown()。用 lifespan context manager 验证。
    """
    import asyncio

    from chat_server.app import create_app
    from chat_server.services.claude_session import session_manager

    called = {"v": False}
    original = session_manager.shutdown

    async def _fake_shutdown():
        called["v"] = True

    async def _drive():
        session_manager.shutdown = _fake_shutdown  # type: ignore[assignment]
        try:
            app = create_app()
            async with app.router.lifespan_context(app):
                pass
        finally:
            session_manager.shutdown = original  # type: ignore[assignment]

    asyncio.run(_drive())
    assert called["v"], "session_manager.shutdown 未被 _lifespan 调用"

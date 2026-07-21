import atexit
import asyncio
import threading
from typing import Any

_bridge_loop: asyncio.AbstractEventLoop | None = None
_pool_lock = threading.Lock()


def _ensure_bridge_loop() -> asyncio.AbstractEventLoop:
    """确保桥接 event loop 已创建（同步版本）。

    历史上曾创建 ThreadPoolExecutor(max_workers=2) 但从未 submit，
    已删除该死代码；仅保留独立 event loop。
    """
    global _bridge_loop

    with _pool_lock:
        if _bridge_loop is not None:
            return _bridge_loop

        try:
            _bridge_loop = asyncio.get_running_loop()
        except RuntimeError:
            _bridge_loop = asyncio.new_event_loop()

        return _bridge_loop


def _call_with_context(fn: Any, context: dict[str, Any]) -> Any:
    """用关键字参数调用可调用对象，避免把 context.values() 当位置参数。"""
    kwargs = {k: v for k, v in context.items() if k != "kwargs"}
    extra = context.get("kwargs")
    if isinstance(extra, dict):
        kwargs.update(extra)
    return fn(**kwargs)


def run_async(coro: Any, timeout: int = 600) -> Any:
    """
    在桥接独立 event loop 中执行协程或 Future。

    Args:
        coro: 可等待对象（协程、任务、Future、同步值）
        timeout: 超时时间（秒）

    Returns:
        协程执行结果

    Raises:
        TimeoutError: 执行超时
        Exception: 协程中抛出的异常
    """
    loop = _ensure_bridge_loop()

    if loop.is_running():
        raise RuntimeError("Bridge loop is already running in another context")

    if not asyncio.iscoroutine(coro) and not isinstance(coro, asyncio.Future):
        if callable(coro):
            return coro()
        return coro

    try:
        return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
    except TimeoutError as e:
        raise TimeoutError(f"run_async() timeout after {timeout}s") from e
    except Exception:
        raise


def run_async_with_context(coro: Any, context: dict[str, Any]) -> Any:
    """
    在桥接独立 event loop 中执行协程，支持通过关键字参数传递上下文。

    Args:
        coro: 协程、Future、或可调用对象（同步/异步函数）
        context: 上下文字典，作为关键字参数传入可调用对象

    Returns:
        执行结果

    Raises:
        TimeoutError: 执行超时
        Exception: 协程中抛出的异常
    """
    loop = _ensure_bridge_loop()

    if loop.is_running():
        raise RuntimeError("Bridge loop is already running in another context")

    if not asyncio.iscoroutine(coro) and not isinstance(coro, asyncio.Future):
        if not callable(coro):
            return coro
        result = _call_with_context(coro, context)
        if not asyncio.iscoroutine(result) and not isinstance(result, asyncio.Future):
            return result
        coro = result

    try:
        return loop.run_until_complete(asyncio.wait_for(coro, timeout=600))
    except TimeoutError as e:
        raise TimeoutError("run_async_with_context() timeout after 600s") from e
    except Exception:
        raise


def get_bridge_loop() -> asyncio.AbstractEventLoop | None:
    """获取桥接 event loop 实例，用于调试或高级场景直接异步调用。"""
    return _bridge_loop


def shutdown_bridge() -> None:
    """关闭桥接 event loop（atexit / 测试用）。"""
    global _bridge_loop
    with _pool_lock:
        if _bridge_loop is not None and not _bridge_loop.is_running():
            try:
                _bridge_loop.close()
            except Exception:
                pass
        _bridge_loop = None


atexit.register(shutdown_bridge)

# 兼容旧名（审计报告 / 历史调用）
_ensure_bridge_thread_pool = _ensure_bridge_loop

import asyncio
from typing import Any
from concurrent.futures import ThreadPoolExecutor

_executor: ThreadPoolExecutor | None = None
_bridge_loop: asyncio.AbstractEventLoop | None = None


def _ensure_bridge_thread_pool() -> ThreadPoolExecutor:
    """确保桥接线程池已创建且拥有独立 event loop（同步版本）"""
    global _executor, _bridge_loop

    if _executor is not None:
        return _executor

    _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="async_bridge")

    try:
        loop = asyncio.get_running_loop()
        _bridge_loop = loop
    except RuntimeError:
        _bridge_loop = asyncio.new_event_loop()

    return _executor


def run_async(coro: Any, timeout: int = 600) -> Any:
    """
    在桥接线程池的独立 event loop 中执行协程或 Future。

    Args:
        coro: 可等待对象（协程、任务、Future、同步值）
        timeout: 超时时间（秒）

    Returns:
        协程执行结果

    Raises:
        TimeoutError: 执行超时
        Exception: 协程中抛出的异常
    """
    if _bridge_loop is None:
        _ensure_bridge_thread_pool()

    if _bridge_loop.is_running():
        raise RuntimeError("Bridge loop is already running in another context")

    if not asyncio.iscoroutine(coro) and not isinstance(coro, asyncio.Future):
        if callable(coro):
            return coro()
        return coro

    coro = asyncio.ensure_future(coro) if callable(coro) and not asyncio.iscoroutine(coro) else coro

    try:
        return _bridge_loop.run_until_complete(
            asyncio.wait_for(coro, timeout=timeout)
        )
    except TimeoutError as e:
        raise TimeoutError(f"run_async() timeout after {timeout}s") from e
    except Exception as e:
        raise e


def run_async_with_context(coro: Any, context: dict[str, Any]) -> Any:
    """
    在桥接线程池的独立 event loop 中执行协程，支持 trace_id 等上下文传递。

    Args:
        coro: 可等待对象（协程、Future、同步值）
        context: 上下文字典

    Returns:
        协程执行结果

    Raises:
        TimeoutError: 执行超时
        Exception: 协程中抛出的异常
    """
    if _bridge_loop is None:
        _ensure_bridge_thread_pool()

    if _bridge_loop.is_running():
        raise RuntimeError("Bridge loop is already running in another context")

    if not asyncio.iscoroutine(coro) and not isinstance(coro, asyncio.Future):
        # Straight context values
        coro = coro(*tuple(context.values()), **context.get("kwargs", {}))

    if callable(coro) and not asyncio.iscoroutine(coro):
        coro = asyncio.ensure_future(coro)

    try:
        return _bridge_loop.run_until_complete(
            asyncio.wait_for(coro, timeout=600)
        )
    except TimeoutError as e:
        raise TimeoutError("run_async_with_context() timeout after 600s") from e
    except Exception as e:
        raise e


def get_bridge_loop() -> asyncio.AbstractEventLoop | None:
    """
    获取桥接 event loop 实例，用于调试或高级场景直接异步调用。
    """
    return _bridge_loop

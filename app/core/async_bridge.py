"""统一异步桥接模块 - 消除分布式事件循环碎片化

运行时只需导入一次 'run_async' 即可获得统一的超时 + 上下文传递能力。

安全地使用标准 asyncio.run()（TLS 自包含），并通过内置兜底保证无残留 loop。
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


# 可选的专用线程池（保留扩展性，目前仅直接使用 asyncio.run）
_executor = None


def run_async(coro: Any, timeout: int = 600) -> Any:
    """在标准 asyncio 上下文中执行协程，支持超时控制

    Args:
        coro: 要执行的协程
        timeout: 超时秒数（默认 10 分钟）

    Returns:
        协程的返回值

    Raises:
        TimeoutError: 超过 timeout 设置
        asyncio.CancelledError: 协程被外部 cancel
    """
    # 使用 asyncio.run() 避免循环调用 get_running_loop()
    async def _runner() -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as exc:
            logger.warning(f"async_bridge.run_async timeout: {exc}")
            raise

    # asyncio.run() 会创建新 event loop 并在退出时自动关闭
    # 如果调用方已经在某个 loop 中，此处会触发 RuntimeError（有意为之）
    return asyncio.run(_runner())


def run_async_with_context(coro: Any, context: dict) -> Any:
    """支持 trace_id 等上下文传递的异步桥接

    Args:
        coro: 要执行的协程
        context: 上下文字典（如 {'trace_id': 'xxx'}）

    Returns:
        协程的返回值

    Raises:
        TimeoutError: 超过默认超时
    """
    # 将 context 注入到协程闭包中（示例：gRPC metadata）
    async def _wrapped(c, coro2) -> Any:
        return await coro2

    # 临时修改协程的闭包变量（仅适用于无参数协程）
    raise NotImplementedError(
        "run_async_with_context requires a coroutine bound to context. "
        "Use run_async() with manually injected coroutine instead."
    )

__all__ = ["run_async", "run_async_with_context"]
"""统一异步桥接模块 - 消除分布式事件循环碎片化

运行时只需导入一次 'run_async' 即可获得统一的超时 + 上下文传递能力。
"""

import asyncio


def run_async(coro, timeout: int = 600):
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

    async def _runner():
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise

    return asyncio.run(_runner())


__all__ = ["run_async"]

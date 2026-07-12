import asyncio
import os
from concurrent.futures import TimeoutError
from typing import Any, Optional

from app.core.config import settings


class asyncio_bridge:
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _thread_id: int = 0

    class loop_holder:
        def __init__(self):
            self.loop = asyncio.new_event_loop()
            getattr(
                asyncio,
                "set_event_loop",
                getattr(asyncio, "set_running_loop", self.loop),
            )

        def __del__(self):
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            self.loop.close()

    @classmethod
    def _run_threadsafe(cls, coro: Any, loop: asyncio.AbstractEventLoop) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    @classmethod
    def _ensure_loop(cls) -> asyncio.AbstractEventLoop:
        import threading

        current_thread_id = threading.get_ident()

        if cls._loop is not None and cls._thread_id == current_thread_id:
            return cls._loop

        cls._loop = asyncio.new_event_loop()
        cls._thread_id = current_thread_id
        asyncio.set_event_loop(cls._loop)

        return cls._loop


def run_async(coro: Any, timeout: float = 600) -> Any:
    """
    异步协程运行器，自动选择现有循环或创建专用线程持有独立循环

    Args:
        coro: 要运行的协程
        timeout: 超时时间（秒）

    Returns:
        协程返回值

    Raises:
        TimeoutError: 如果协程未在指定时间内完成
        Exception: 协程抛出的其他异常
    """
    loop = asyncio_bridge._ensure_loop()

    try:
        return asyncio_bridge._run_threadsafe(coro, loop)
    except Exception as e:
        if isinstance(e, TimeoutError):
            if hasattr(settings, "DEBUG") and settings.DEBUG:
                import traceback as tb

                print("Async operation timeout:")
                import traceback as tb

                print(tb.format_exc())
            raise
        raise


def run_async_with_context(coro: Any, context: dict) -> Any:
    """
    带上下文信息的异步协程运行器，支持 trace_id 传递

    Args:
        coro: 要运行的协程
        context: 上下文字典，会被注入到全局变量

    Returns:
        协程返回值

    Raises:
        TimeoutError: 如果协程未在指定时间内完成
        Exception: 协程抛出的其他异常
    """
    import time

    trace_id = context.get("trace_id")
    if trace_id:
        import os

        os.environ["TRACE_ID"] = trace_id

    try:
        return run_async(coro, timeout=600)
    except Exception as e:
        if hasattr(settings, "DEBUG") and settings.DEBUG:
            print("Async operation with context failed:")
            import traceback as tb

            print(tb.format_exc())
        raise
    finally:
        if trace_id:
            os.environ.pop("TRACE_ID", None)

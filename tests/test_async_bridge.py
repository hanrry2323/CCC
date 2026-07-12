import asyncio
import pytest
from app.core.async_bridge import run_async, run_async_with_context, get_bridge_loop, _ensure_bridge_thread_pool


def test_ensure_bridge_thread_pool_created():
    """测试桥接线程池创建"""
    pool = _ensure_bridge_thread_pool()
    assert pool is not None
    assert isinstance(pool, type(pool))


def test_get_bridge_loop():
    """测试获取桥接 loop 实例"""
    loop = get_bridge_loop()
    assert loop is not None
    assert isinstance(loop, asyncio.AbstractEventLoop)


def test_run_sync_value():
    """测试同步值"""
    def sync_func():
        return "sync_success"

    result = run_async(sync_func, timeout=1)
    assert result == "sync_success"


def test_run_sync_val():
    """测试直接同步值"""
    result = run_async("direct_value", timeout=1)
    assert result == "direct_value"


async def async_func_for_test():
    """用于测试的异步函数"""
    await asyncio.sleep(0.001)
    return "async_result"


def test_run_async_and_await():
    """测试 async + await"""
    result = run_async(async_func_for_test())
    assert result == "async_result"


async def failing_async_for_test():
    """用于测试的失败异步函数"""
    await asyncio.sleep(0.001)
    raise ValueError("test error")


def test_run_async_exception():
    """测试异常传播"""
    with pytest.raises(ValueError, match="test error"):
        run_async(failing_async_for_test())

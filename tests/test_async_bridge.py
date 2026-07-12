# async_bridge 统一桥接测试

import asyncio
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.async_bridge import run_async


async def dummy_async():  # noqa: D401
    """无返回值的简单协程"""
    await asyncio.sleep(0.1)
    return "success"


async def failing_async():  # noqa: D401
    """会失败的协程"""
    await asyncio.sleep(0.1)
    raise ValueError("intentional failure")


async def timeout_async():  # noqa: D401
    """超时协程"""
    await asyncio.sleep(120)
    return "should be canceled"


def test_run_async_success():
    """正常执行且返回值的测试"""
    result = run_async(dummy_async())
    assert result == "success"
    print("✅ test_run_async_success passed")


def test_run_async_timeout():
    """超时控制的测试"""
    try:
        run_async(timeout_async(), timeout=int(0.2))  # noqa: E501, type: ignore
        assert False, "Should raise TimeoutError"
    except Exception as exc:
        assert "TimeoutError" in str(type(exc))
        print("✅ test_run_async_timeout passed")


def test_run_async_failure():
    """异常传播的测试"""
    try:
        run_async(failing_async())
        assert False, "Should raise ValueError"
    except ValueError:
        print("✅ test_run_async_failure passed")


if __name__ == "__main__":
    test_run_async_success()
    test_run_async_timeout()
    test_run_async_failure()
    print("All tests passed! ✅")

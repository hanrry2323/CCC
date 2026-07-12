"""Test async bridge module: exceptions, timeout, thread-safe execution"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / ".."))

from scripts._config import get_logger
from app.core.async_bridge import run_async, run_async_with_context

_log = get_logger("test_async_bridge")


async def successful_coro():
    """Should complete successfully"""
    await asyncio.sleep(0.1)
    return "success"


async def failed_coro():
    """Should raise an exception"""
    await asyncio.sleep(0.1)
    raise ValueError("Test exception")


async def timeout_coro():
    """Should timeout"""
    await asyncio.sleep(5)
    return "should not reach"


async def context_coro(context):
    """Should access context vars"""
    import uuid as _uuid

    trace_id = context.get("trace_id")
    if trace_id is None:
        trace_id = _uuid.uuid4().hex[:8]

    context["trace_id"] = trace_id
    context["captured_trace"] = trace_id

    await asyncio.sleep(0.1)
    return {"trace_id": trace_id, "seen_trace": context.get("seen_trace")}


def test_successful_async():
    """Test basic successful execution"""
    result = run_async(successful_coro())
    assert result == "success", f"Expected 'success', got {result}"
    print("✓ test_successful_async passed")


def test_failed_async():
    """Test exception handling"""
    try:
        run_async(failed_coro())
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert str(e) == "Test exception"
        print("✓ test_failed_async passed")


def test_timeout():
    """Test timeout handling"""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            result = run_async(timeout_coro(), timeout=2)
            if result == "should not reach":
                print("✗ test_timeout: should not reach here")
                assert False
        except Exception as e:
            print(f"✓ test_timeout: caught expected exception: {type(e).__name__}")
            assert "timeout" in str(e).lower()


def test_context_injection():
    """Test context injection and trace_id propagation"""
    context = {"trace_id": "test-123"}

    result = run_async_with_context(context_coro, context)

    assert "trace_id" in result
    assert result["trace_id"] == "test-123"
    assert result["seen_trace"] == "test-123"
    print("✓ test_context_injection passed")


def test_thread_safety():
    """Test execution in different threads"""
    results = []

    def worker():
        result = run_async(successful_coro())
        results.append(result)
        return result

    import threading

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5
    assert all(r == "success" for r in results)
    print("✓ test_thread_safety passed")


def main():
    print("Running async bridge tests...")
    test_successful_async()
    test_failed_async()

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", asyncio.TimeoutError)
        test_timeout()

    test_context_injection()
    test_thread_safety()
    print("\n✓ All tests passed!")


if __name__ == "__main__":
    main()

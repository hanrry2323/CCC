"""lib/retry.py — 通用指数退避重试装饰器。

设计：
  * 零外部依赖（仅 stdlib）
  * 指数退避 + jitter（默认 ±10%）
  * 重试满 max_attempts 后写死信文件 + 重新 raise
  * 保留被装饰函数的签名/文档（functools.wraps）

用法：
    from lib.retry import retry

    @retry(max_attempts=3, backoff=2.0, jitter=0.1)
    def fetch(url):
        return requests.get(url, timeout=10).json()
"""

from __future__ import annotations

import functools
import random
import time
from typing import Callable, Iterable, Tuple, Type, TypeVar

T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    dead_letter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """指数退避 + jitter 重试装饰器。

    Args:
        max_attempts: 最多尝试次数（含首次失败也算一次）。
        backoff: 退避基数。第 N 次重试前 sleep `backoff ** N` 秒。
        jitter: 抖动比例。0 表示无抖动；0.1 表示 ±10%。
        exceptions: 触发重试的异常类型元组。
        dead_letter: 重试满后是否调用 lib.dead_letter.write_dead_letter。
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt >= max_attempts:
                        break
                    base_sleep = backoff**attempt
                    jitter_range = base_sleep * jitter
                    delay = base_sleep + random.uniform(-jitter_range, jitter_range)
                    delay = max(0.0, delay)
                    time.sleep(delay)
            # 所有尝试都失败 —— 写死信 + raise
            assert last_exc is not None
            if dead_letter:
                try:
                    from lib.dead_letter import write_dead_letter

                    write_dead_letter(
                        func_name=getattr(func, "__qualname__", func.__name__),
                        module=getattr(func, "__module__", ""),
                        exc=last_exc,
                        args=args,
                        kwargs=kwargs,
                    )
                except Exception:
                    # 死信写入失败不能影响业务抛出
                    pass
            raise last_exc

        return wrapper

    return decorator

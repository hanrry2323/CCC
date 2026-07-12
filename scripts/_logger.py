"""_logger.py — CCC 统一 logger (v0.28.0+)

按红线 R-08 落地：所有 ccc-* 脚本必须用统一 logger，禁止用 print() 冒充日志输出。

设计原则：
1. **统一前缀** [role=xxx] — 便于从 launchd 日志中 grep
2. **可关闭** — 环境变量 CCC_LOG_LEVEL 控制（DEBUG/INFO/WARNING/ERROR）
3. **写 stderr** — 避免与正常 stdout 输出混在一起
4. **极简 API** — get_logger(name) → 5 个标准方法（debug/info/warning/error/exception）

用法：
    from _config import get_logger
    log = get_logger("board")
    log.info("task moved")            # → [board] task moved
    log.warning("retry %d", n)        # → [board] retry 1
    log.exception("crash")            # → 打印堆栈

环境变量：
    CCC_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR  (default INFO)
    CCC_LOG_PREFIX=1                         (default 1, [role=xxx] 前缀开关)

v0.28.1: 默认等级从 WARNING→INFO，使 engine 日志默认可见。
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional


_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

_DEFAULT_LEVEL = "INFO"


def _resolve_level() -> int:
    """环境变量 CCC_LOG_LEVEL → 整型 level，默认 WARNING。"""
    raw = os.environ.get("CCC_LOG_LEVEL", _DEFAULT_LEVEL).strip().upper()
    return _LEVELS.get(raw, logging.WARNING)


def _resolve_prefix_enabled() -> bool:
    """环境变量 CCC_LOG_PREFIX=0 可关闭 [role=xxx] 前缀。"""
    raw = os.environ.get("CCC_LOG_PREFIX", "1").strip()
    return raw not in ("0", "false", "False", "no", "NO")


_configured = False


def _configure_root() -> None:
    """配置 root logger — 每个进程只配置一次。"""
    global _configured
    if _configured:
        return
    _configured = True
    root = logging.getLogger("ccc")
    root.setLevel(_resolve_level())
    # 防止重复 handler（reload 场景）
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    root.addHandler(handler)
    root.propagate = False


class _CCCLogger:
    """轻量包装 — 简化调用，让 log.info(x) 比 logging.getLogger().info(x) 短。

    内部走标准 logging 模块（共享 root 的 level / handler）。
    """

    __slots__ = ("_log", "_name", "_prefix_enabled")

    def __init__(self, name: str, prefix_enabled: bool = True):
        _configure_root()
        self._log = logging.getLogger(f"ccc.{name}")
        self._name = name
        self._prefix_enabled = prefix_enabled

    def _format(self, msg: str) -> str:
        # 在 logging.Formatter 之外额外加 role= 前缀（细粒度定位）
        if self._prefix_enabled:
            return f"role={self._name}] {msg}"
        return msg

    # 注：handler 的 Formatter 已是 "[%(name)s] %(message)s"，name 包含 ccc. 前缀
    # 这里改走传 args 路径，避免双重格式化。重新设计：直接用 logging 的 extra
    # 但为兼容既有调用 log.info("task %s", t)，保持*args。
    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log.error(msg, *args, **kwargs)

    def exception(self, msg: str, *args, exc_info: bool = True, **kwargs) -> None:
        """记录异常堆栈。exc_info 默认 True（与标准库不同：CCC 默认打印堆栈）"""
        self._log.exception(msg, *args, **kwargs) if exc_info else self._log.error(msg, *args, **kwargs)


def get_logger(name: str) -> _CCCLogger:
    """获取 CCC logger 实例。name 通常为角色名（board / engine / store / ...）。"""
    return _CCCLogger(name, prefix_enabled=_resolve_prefix_enabled())


def reset_for_test() -> None:
    """测试辅助：重置 _configured 标志。"""
    global _configured
    _configured = False
    root = logging.getLogger("ccc")
    for h in list(root.handlers):
        root.removeHandler(h)

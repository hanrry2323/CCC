"""CCC 多执行面插件包。契约：docs/product/executor-plugins.md"""

from .registry import EXECUTOR_IDS, resolve_executor, run_executor

__all__ = ["EXECUTOR_IDS", "resolve_executor", "run_executor"]

"""_exceptions.py — CCC 自定义异常 (v0.28.1+)

领域异常集中定义，便于调用方捕获与日志归类。
"""

from __future__ import annotations


class CCCError(Exception):
    """CCC 基础异常"""


class CCCConfigError(CCCError):
    """配置解析或环境变量错误"""


class CCCBoardError(CCCError):
    """看板读写、流转或校验错误"""


class CCCLockError(CCCBoardError):
    """文件锁获取或释放失败"""


class CCCExecutorError(CCCError):
    """OpenCode / 子进程执行错误"""


class CCCReviewError(CCCError):
    """代码审查或 verdict 流程错误"""

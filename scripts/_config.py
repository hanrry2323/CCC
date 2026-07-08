"""ccc — 集中配置 (v0.19)

所有 CCC 配置参数集中于此。任何脚本需要配置参数时，从这里导入，而不是硬编码。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """CCC 全局配置

    所有字段都有默认值，环境变量优先于默认值。
    使用方式:
        from _config import Config
        cfg = Config()
        print(cfg.model)
    """

    # ── 路径 ──
    ccc_home: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )
    workspace: Path = field(default_factory=lambda: _resolve_workspace())
    # 被 board-server.py 依赖的 board_path 函数使用

    # ── 模型 ──
    model: str = "loop/flash"  # 所有子进程默认模型

    # ── 超时 ──
    default_timeout: int = 600  # 秒，phases 默认超时
    hook_timeout: int = 30  # 秒，钩子默认超时

    # ── 容错 ──
    max_retry: int = 5  # 最大重试次数 → 异常隔离
    max_stale_hours: int = 6  # in_progress 卡住超时 → 异常隔离

    # ── 并发 ──
    opencode_max_parallel: int = 3  # 红线 X1

    # ── HTTP 服务 ──
    board_port: int = 7777
    board_host: str = "127.0.0.1"

    def __post_init__(self):
        """环境变量覆盖（优先级：环境变量 > 默认值）"""
        _env_override_int(self, "default_timeout", "CCC_TIMEOUT")
        _env_override_int(self, "hook_timeout", "CCC_HOOK_TIMEOUT")
        _env_override_int(self, "max_retry", "CCC_MAX_RETRY")
        _env_override_int(self, "max_stale_hours", "CCC_STALE_HOURS")
        _env_override_str(self, "model", "OPENCODE_MODEL")
        _env_override_str(self, "board_host", "BOARD_HOST")
        _env_override_int(self, "board_port", "BOARD_PORT")


def _resolve_workspace() -> Path:
    """优先环境变量 CCC_WORKSPACE，否则默认为 ccc_home"""
    env = os.environ.get("CCC_WORKSPACE", "").strip()
    if env:
        return Path(env)
    ccc_path = Path(__file__).resolve().parent.parent
    return ccc_path


def _env_override_int(cfg: Config, attr: str, env_key: str) -> None:
    val = os.environ.get(env_key, "").strip()
    if val:
        try:
            setattr(cfg, attr, int(val))
        except ValueError:
            pass


def _env_override_str(cfg: Config, attr: str, env_key: str) -> None:
    val = os.environ.get(env_key, "").strip()
    if val:
        setattr(cfg, attr, val)

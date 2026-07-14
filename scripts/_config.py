"""ccc — 集中配置 (v0.28.0)

所有 CCC 配置参数集中于此。任何脚本需要配置参数时，从这里导入，而不是硬编码。

v0.28.0 新增：
- default_timeout 默认 600 → 1800
- 支持 CCC_TIMEOUT / CCC_HOOK_TIMEOUT duration 类 expr（如 "15m" / "1h"）
- timeout 范围 clamp [60, 86400]
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from _logger import get_logger

_log = get_logger("config")

# 统一入口：脚本应 `from _config import get_logger`
__all__ = ["Config", "get_logger", "parse_duration", "TIMEOUT_MIN", "TIMEOUT_MAX"]


_DURATION_RE = re.compile(r"^(\d+)\s*(s|sec|m|min|h|hr|d|day)?$", re.IGNORECASE)
_DURATION_UNITS = {
    "s": 1,
    "sec": 1,
    "m": 60,
    "min": 60,
    "h": 3600,
    "hr": 3600,
    "d": 86400,
    "day": 86400,
}
TIMEOUT_MIN = 60
TIMEOUT_MAX = 86400


def parse_duration(value, default: int) -> int:
    """解析 duration 类表达式为秒数。

    支持：
    - int (直接返回)
    - "300" → 300
    - "5m" / "5min" → 300
    - "2h" / "2hr" → 7200
    - "1d" / "1day" → 86400

    越界 clamp 到 [60, 86400]。
    """
    if isinstance(value, int):
        return max(TIMEOUT_MIN, min(TIMEOUT_MAX, value))
    if not value:
        return max(TIMEOUT_MIN, min(TIMEOUT_MAX, default))
    s = str(value).strip()
    m = _DURATION_RE.match(s)
    if not m:
        try:
            n = int(s)
            if n <= 0:
                return max(TIMEOUT_MIN, min(TIMEOUT_MAX, default))
            return max(TIMEOUT_MIN, min(TIMEOUT_MAX, n))
        except ValueError:
            return max(TIMEOUT_MIN, min(TIMEOUT_MAX, default))
    n = int(m.group(1))
    unit = (m.group(2) or "s").lower()
    if n <= 0 or unit not in _DURATION_UNITS:
        return TIMEOUT_MIN
    # v0.28.0: 先 clamp n 防溢出，再乘单位
    max_n = TIMEOUT_MAX // _DURATION_UNITS[unit]
    n = max(1, min(n, max_n))
    return max(TIMEOUT_MIN, min(TIMEOUT_MAX, n * _DURATION_UNITS[unit]))


@dataclass
class ModelTier:
    """模型梯队配置"""

    name: str
    description: str
    default_provider: str  # 中转站模型名
    fallback_providers: list[str]  # 降级链, 优先级从高到低
    timeout_scale: float = 1.0  # 相对基准超时倍率
    max_retries: int = 3


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
    model: str = "loop/code"  # dev_role 默认模型（opencode run --model），可用 OPENCODE_MODEL 覆盖

    # ── 标准默认值 ──
    DEFAULT_RETRY: int = 3  # phase 默认重试次数（无 retry 字段时用）
    DEFAULT_TIMEOUT: int = 600  # 秒，phase/执行层默认超时（v0.28.0: 600s）

    # ── 超时（v0.28.0）──
    default_timeout: int = 1800  # 秒，phases 默认超时（v0.27.1=600 → v0.28.0=1800）
    hook_timeout: int = 30  # 秒，钩子默认超时
    phase_timeout: int = 600  # 秒，phase 执行超时（用于 engine polling）
    exec_timeout: int = 300  # 秒，exec 任务执行超时（opencode-exec）
    reviewer_timeout: int = 600  # 秒，reviewer LLM 调用超时（large diff 需要更长）
    engine_tick_interval: int = 5  # 秒，engine idle sleep 时间

    # ── 容错 ──
    max_retry: int = 5  # 最大重试次数 → 异常隔离
    max_stale_hours: int = 6  # in_progress 卡住超时 → 异常隔离

    # ── 并发 ──
    opencode_max_parallel: int = 3  # 红线 X1

    # ── 引擎（v0.20.1）──
    engine_poll_interval: int = 10  # 秒，活跃 task 时轮询 .done 间隔
    engine_idle_sleep: int = 5  # 秒，无 task 时休眠间隔

    # ── 大变更（v0.28.0 F2-M1）──
    size_hint_threshold: int = 100  # plan 加权分 > 此值注入大变更提示

    # ── auto_approve（v0.28.0 F4-M1）──
    auto_approve_max_per_run: int = 10  # 每次最多合入建议数

    # ── reviewer 超时重试（v0.31+）──
    reviewer_retry_on_timeout: int = (
        3  # reviewer LLM 超时最大重试次数（含首次），超过则 quarantine
    )

    # ── product_role ──
    max_phases: int = 2  # product_role 拆解 task 的最大 phase 数，超出抛异常

    # ── 模型梯队（v0.31）──
    model_tiers: dict[str, ModelTier] = field(
        default_factory=lambda: {
            "pro": ModelTier(
                name="pro",
                description="高端模型 - 架构设计 / 重构 / 审查",
                default_provider="sonnet",
                fallback_providers=[],
                timeout_scale=2.0,
                max_retries=5,
            ),
            "flash": ModelTier(
                name="flash",
                description="主力模型 - 日常开发 / 拆任务 / 对话",
                default_provider="deepseek-v4-flash",
                fallback_providers=["deepseek-v4-flash"],
                timeout_scale=1.0,
                max_retries=3,
            ),
            "code": ModelTier(
                name="code",
                description="免费模型 - 自动化开发 bulk 工作",
                default_provider="MiniMax-M3",
                fallback_providers=["xfyun-code", "zhipu-glm47-flash"],
                timeout_scale=1.5,
                max_retries=3,
            ),
        }
    )

    # ── 审计（v0.22）──
    audit_interval_hours: int = 2  # audit_role 调用最小间隔
    audit_workspaces: list[str] = field(  # audit_role 扫描的多 workspace
        default_factory=lambda: _default_workspaces()
    )

    # ── HTTP 服务 ──
    board_port: int = 7777
    board_host: str = "127.0.0.1"
    engine_stats_port: int = 7776  # ccc-engine.py 内置 stats 端点

    # ── Webhook（v0.32+）──
    webhook_url: str = (
        ""  # Patrol webhook URL，留空禁用；优先级 CCC_WEBHOOK_URL 环境变量
    )

    def __post_init__(self):
        """环境变量覆盖（优先级：环境变量 > 默认值）

        v0.28.0: timeout 支持 duration 类 expr（5m / 1h / 1d）和 clamp [60, 86400]
        """
        _env_override_duration(
            self, "default_timeout", "CCC_TIMEOUT", self.default_timeout
        )
        _env_override_duration(
            self, "hook_timeout", "CCC_HOOK_TIMEOUT", self.hook_timeout
        )
        _env_override_int(self, "max_retry", "CCC_MAX_RETRY")
        _env_override_int(self, "max_stale_hours", "CCC_STALE_HOURS")
        _env_override_str(self, "model", "OPENCODE_MODEL")
        _env_override_str(self, "board_host", "BOARD_HOST")
        _env_override_int(self, "board_port", "BOARD_PORT")
        _env_override_int(self, "engine_stats_port", "CCC_ENGINE_STATS_PORT")
        _env_override_int(self, "engine_poll_interval", "CCC_ENGINE_POLL_INTERVAL")
        _env_override_int(self, "engine_idle_sleep", "CCC_ENGINE_IDLE_SLEEP")
        _env_override_int(self, "phase_timeout", "CCC_PHASE_TIMEOUT")
        _env_override_int(self, "exec_timeout", "CCC_EXEC_TIMEOUT")
        _env_override_int(self, "reviewer_timeout", "CCC_REVIEWER_TIMEOUT")
        _env_override_int(self, "engine_tick_interval", "CCC_ENGINE_TICK_INTERVAL")
        _env_override_int(self, "max_phases", "CCC_MAX_PHASES")
        _env_override_int(self, "reviewer_retry_on_timeout", "CCC_REVIEWER_RETRY")
        _env_override_str(self, "webhook_url", "CCC_WEBHOOK_URL")


def _resolve_workspace() -> Path:
    """优先环境变量 CCC_WORKSPACE，否则默认为 ccc_home"""
    env = os.environ.get("CCC_WORKSPACE", "").strip()
    if env:
        p = Path(env).resolve()
        if p.is_absolute():
            return p
    ccc_path = Path(__file__).resolve().parent.parent
    return ccc_path


def _default_workspaces() -> list[str]:
    """audit_role 扫描的 workspace 列表

    优先环境变量 CCC_AUDIT_WORKSPACES（逗号分隔），否则扫描 ~/program/ 下含 .ccc/board 的项目。
    """
    env = os.environ.get("CCC_AUDIT_WORKSPACES", "").strip()
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]
    program_dir = Path.home() / "program"
    if not program_dir.is_dir():
        return []
    found: list[str] = []
    for sub in program_dir.iterdir():
        if not sub.is_dir():
            continue
        if (sub / ".ccc" / "board").exists():
            found.append(str(sub))
    projects = program_dir / "projects"
    if projects.is_dir():
        for sub in projects.iterdir():
            if not sub.is_dir():
                continue
            if (sub / ".ccc" / "board").exists():
                found.append(str(sub))
    return found


def _env_override_int(cfg: Config, attr: str, env_key: str) -> None:
    val = os.environ.get(env_key, "").strip()
    if val:
        try:
            setattr(cfg, attr, int(val))
        except ValueError:
            _log.warning("invalid %s=%r, keeping default", env_key, val, exc_info=True)


def _env_override_str(cfg: Config, attr: str, env_key: str) -> None:
    val = os.environ.get(env_key, "").strip()
    if val:
        setattr(cfg, attr, val)


def _env_override_duration(cfg: Config, attr: str, env_key: str, default: int) -> None:
    """v0.28.0: 支持 duration 类 expr 解析（如 "15m" / "1h"）"""
    val = os.environ.get(env_key, "").strip()
    if val:
        setattr(cfg, attr, parse_duration(val, default))

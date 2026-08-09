"""配置加载器 — 从 config.env 加载运行参数，零硬编码。

用法：
    from server.config.loader import load_config, ConfigError

    cfg = load_config("server/config/config.env")
    print(cfg["ENGINE_PORT"])
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

# 必填键列表（对应 config.example.env）
REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "ENGINE_PORT",
        "BOARD_PORT",
        "WEB_PORT",
        "RELAY_PORT",
        "DATA_DIR",
        "LOG_DIR",
        "RELAY_UPSTREAM_URL",
        "EXECUTOR_REGISTRY_PATH",
    }
)

# 可选键（有默认值）
OPTIONAL_KEYS: dict[str, str] = {
    "RELAY_UPSTREAM_KEY": "",
    "PYTHON_BIN": "",
    # 定时任务框架
    "SCHEDULER_INTERVAL": "60",
    "SCHEDULER_DISPATCH_DIR": "",
    # 集群采集
    "CLUSTER_TARGETS": "",
    "CLUSTER_SERVICES": "",
    # 中转站部署模板占位（T4，部署前手动替换，可选）
    "CCC_RELAY_PROJECT_ROOT": "",
    "LOOP_ANTHROPIC_PORT": "",
    "LOOP_OPENAI_PORT": "",
    "NODE_BIN": "",
    # 执行体派发运行参数（T32 真实派发闭环）
    "EXECUTOR_TIMEOUT_SECONDS": "300",
    "EXECUTOR_LOG_DIR": "",
    # 任务卡目录（P1-1 FileBoardStore 读写；默认 docs/dispatch）
    "DISPATCH_DIR": "docs/dispatch",
    # 执行槽上限（独立于机审槽；执行与机审互不占位）
    "EXECUTOR_MAX_CONCURRENT": "3",
    # 双脑编排并发上限（config.example.env 有声明但此前未加载，2026-08-10 补）
    "CCC_BRAIN_MAX_CONCURRENCY": "2",
    # 机审槽上限（独立于执行槽）
    "EXECUTOR_MAX_AUDIT_CONCURRENT": "2",
    "EXECUTOR_PROBE_URL": "http://127.0.0.1:6100/",
    "EXECUTOR_RETRY_ONCE": "true",
    # 失败回待分派自动重试上限；用尽才打回。RETRY_ONCE=false 时视为 0
    "EXECUTOR_MAX_RETRIES": "3",
    # 基础设施故障（上游/网络/超时）冷却秒数：冷却内不重试、不计业务重试预算、不打回
    "EXECUTOR_INFRA_COOLDOWN_SECONDS": "60",
    # 基础设施连续失败最大重试次数熔断打回门槛（默认 5）
    "EXECUTOR_INFRA_MAX_STRIKES": "5",
    # 基础设施连续失败冷却秒数封顶退避秒数（默认 1800）
    "EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS": "1800",
    # 机审超时秒数（独立于执行超时；防挂起审计长期占槽，默认 30 分钟）
    "EXECUTOR_AUDIT_TIMEOUT_SECONDS": "1800",
    # 生产仓自动 git 对齐（人只 push；2017 Engine/看板自 pull）
    "CCC_AUTO_PULL": "1",
    "CCC_AUTO_PULL_REMOTE": "origin",
    "CCC_AUTO_PULL_BRANCH": "main",
    # 大脑知识库检索（T37：/conversation 回答前检索 CCC 自建知识库）
    "CCC_BRAIN_KB": "0",
    "CCC_KB_INDEX_DIR": "",
    "CCC_BRAIN_KB_TOP_K": "3",
}

LINE_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*(.*?)\s*$")


class ConfigError(Exception):
    """配置加载错误。"""


def load_config(env_path: str | Path) -> dict[str, Any]:
    """加载 config.env 文件，返回配置字典。

    Args:
        env_path: 配置文件路径。

    Returns:
        配置键值对字典。

    Raises:
        ConfigError: 文件不存在、格式错误、必填项缺失。
    """
    path = Path(env_path).expanduser().resolve()

    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    raw: dict[str, str] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE_RE.match(line)
        if not m:
            raise ConfigError(f"invalid config line {lineno}: {line}")
        key, val = m.group(1), m.group(2)
        raw[key] = val

    missing = REQUIRED_KEYS - raw.keys()
    if missing:
        raise ConfigError(f"missing required config keys: {', '.join(sorted(missing))}")

    empty_required = [k for k in REQUIRED_KEYS if not raw.get(k)]
    if empty_required:
        hint = ""
        if "EXECUTOR_REGISTRY_PATH" in empty_required:
            hint = "；请复制 config/executors.example.json 为 executors.json 并填写路径"
        raise ConfigError(f"required config keys are empty: {', '.join(sorted(empty_required))}{hint}")

    result: dict[str, Any] = {}
    for k in REQUIRED_KEYS:
        result[k] = raw[k]
    for k, default in OPTIONAL_KEYS.items():
        result[k] = raw.get(k, default)

    return result


def load_config_from_env() -> dict[str, Any]:
    """从系统环境变量加载配置（不读文件），用于测试 / 覆盖。"""
    result: dict[str, Any] = {}
    for k in REQUIRED_KEYS:
        val = os.environ.get(k)
        if not val:
            raise ConfigError(f"missing required env var: {k}")
        result[k] = val
    for k, default in OPTIONAL_KEYS.items():
        result[k] = os.environ.get(k, default)
    return result

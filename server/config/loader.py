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
REQUIRED_KEYS: frozenset[str] = frozenset({
    "ENGINE_PORT",
    "BOARD_PORT",
    "WEB_PORT",
    "RELAY_PORT",
    "DATA_DIR",
    "LOG_DIR",
    "RELAY_UPSTREAM_URL",
    "EXECUTOR_REGISTRY_PATH",
})

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
        raise ConfigError(
            f"missing required config keys: {', '.join(sorted(missing))}"
        )

    empty_required = [k for k in REQUIRED_KEYS if not raw.get(k)]
    if empty_required:
        hint = ""
        if "EXECUTOR_REGISTRY_PATH" in empty_required:
            hint = "；请复制 config/executors.example.json 为 executors.json 并填写路径"
        raise ConfigError(
            f"required config keys are empty: {', '.join(sorted(empty_required))}"
            f"{hint}"
        )

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

"""Engine 管道静默故障落盘，供 /ops/summary 展示（老板面可见）。

探活跳过 / git sync 失败等不应只写日志；写到 EXECUTOR_LOG_DIR 旁的
``engine-pipeline.json``，HTTP 运维页并入 human_line。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.engine.pipeline_status")

STATUS_FILENAME = "engine-pipeline.json"


def status_path(log_dir: str | Path) -> Path:
    """``{EXECUTOR_LOG_DIR}/../engine-pipeline.json``（与 exec 日志同级树）。"""
    return Path(log_dir).expanduser().resolve().parent / STATUS_FILENAME


def write_pipeline_status(log_dir: str | Path, payload: dict[str, Any]) -> Path | None:
    """原子写管道状态；失败只打日志，不抛。"""
    path = status_path(log_dir)
    body = {
        **payload,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pid": os.getpid(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return path
    except OSError:
        logger.exception("写管道状态失败: %s", path)
        return None


def read_pipeline_status(log_dir: str | Path | None = None) -> dict[str, Any] | None:
    """读管道状态；路径优先参数，否则 ``EXECUTOR_LOG_DIR`` 推导，再试常见默认。"""
    candidates: list[Path] = []
    if log_dir:
        candidates.append(status_path(log_dir))
    env = os.environ.get("EXECUTOR_LOG_DIR", "").strip()
    if env:
        candidates.append(status_path(env))
    # 2017 常见布局
    candidates.append(Path.home() / ".ccc" / "logs" / STATUS_FILENAME)
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            continue
    return None

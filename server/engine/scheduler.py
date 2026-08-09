"""通用定时任务框架 — 间隔调度、只读巡检、变更类走卡。

用法：
    $PYTHON_BIN -m server.engine.scheduler --config <config.env>        # 持续模式
    $PYTHON_BIN -m server.engine.scheduler --config <config.env> --once  # 单次执行后退出

支持两种任务类型：
1. 只读巡检（readonly）：采集状态信息，写入文件，不产生业务动作
2. 变更类（change）：生成任务卡到 dispatch 目录，走正常任务卡流程

定时默认只读：巡检只采集不动作；变更类走任务卡保留确认。
失败时记日志，不中断、不产生脏数据。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from server.config.loader import ConfigError, load_config

logger = logging.getLogger("ccc.engine.scheduler")

DEFAULT_INTERVAL_SECONDS = 60


# ── 任务类型 ──

TASK_TYPE_READONLY = "readonly"
TASK_TYPE_CHANGE = "change"


@dataclass
class ScheduledTask:
    """单个定时任务描述。

    Attributes:
        name: 任务名（日志 / 标识用）。
        task_type: TASK_TYPE_READONLY 或 TASK_TYPE_CHANGE。
        run: 可调用对象，接收 config dict，返回 (ok: bool, summary: dict)。
    """
    name: str
    task_type: str
    run: Callable[[dict[str, Any]], tuple[bool, dict[str, Any]]]


# ── 注册表 ──

@dataclass
class TaskRegistry:
    """定时任务注册表。"""
    tasks: list[ScheduledTask] = field(default_factory=list)

    def register(self, task: ScheduledTask) -> None:
        self.tasks.append(task)

    def list_readonly(self) -> list[ScheduledTask]:
        return [t for t in self.tasks if t.task_type == TASK_TYPE_READONLY]

    def list_change(self) -> list[ScheduledTask]:
        return [t for t in self.tasks if t.task_type == TASK_TYPE_CHANGE]


# ── 执行 ──

def run_tasks(
    registry: TaskRegistry,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """执行所有注册任务，返回结果列表。

    只读巡检总是执行；变更类仅在 SCHEDULER_DISPATCH_DIR 非空时执行。
    """
    results: list[dict[str, Any]] = []
    dispatch_dir = cfg.get("SCHEDULER_DISPATCH_DIR", "")

    for task in registry.list_readonly():
        ok, summary = task.run(cfg)
        results.append({
            "name": task.name,
            "type": task.task_type,
            "ok": ok,
            "summary": summary,
        })
        if ok:
            logger.info("巡检任务 %s 完成: %s", task.name, summary)
        else:
            logger.warning("巡检任务 %s 失败: %s", task.name, summary)

    if dispatch_dir:
        for task in registry.list_change():
            ok, summary = task.run(cfg)
            results.append({
                "name": task.name,
                "type": task.task_type,
                "ok": ok,
                "summary": summary,
            })
            if ok:
                logger.info("变更任务 %s 完成: %s", task.name, summary)
            else:
                logger.warning("变更任务 %s 失败: %s", task.name, summary)
    else:
        for task in registry.list_change():
            logger.info(
                "变更任务 %s 跳过（SCHEDULER_DISPATCH_DIR 未配置）", task.name
            )
            results.append({
                "name": task.name,
                "type": task.task_type,
                "ok": True,
                "summary": {"skipped": True, "reason": "dispatch_dir not configured"},
            })

    return results


# ── CLI ──

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ccc-engine-scheduler",
        description="CCC Engine 定时任务框架：间隔调度、只读巡检、变更类走卡",
    )
    parser.add_argument("--config", required=True, help="config.env 路径（必填）")
    parser.add_argument("--once", action="store_true", help="单次执行后退出")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="覆盖轮询间隔秒数（默认使用 config 中的 SCHEDULER_INTERVAL）",
    )
    return parser.parse_args(argv)


def run_once(
    registry: TaskRegistry,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """单次执行所有注册任务。"""
    return run_tasks(registry, cfg)


def run_loop(
    registry: TaskRegistry,
    cfg: dict[str, Any],
    interval: int,
) -> None:
    """持续模式：每 interval 秒执行一轮。"""
    logger.info("定时任务框架启动（轮询间隔 %ds）", interval)
    while True:
        results = run_tasks(registry, cfg)
        logger.info("本轮任务完成: %s", json.dumps(results, ensure_ascii=False))
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 2

    interval = args.interval if args.interval > 0 else int(cfg.get("SCHEDULER_INTERVAL", DEFAULT_INTERVAL_SECONDS))

    # 注册默认任务（可被外部扩展覆盖）
    registry = _default_registry()

    if args.once:
        results = run_once(registry, cfg)
        print(json.dumps(results, ensure_ascii=False))
        return 0

    run_loop(registry, cfg, interval)
    return 0  # 持续模式不返回（Ctrl-C 终止）


# ── 默认注册表 ──

def _default_registry() -> TaskRegistry:
    """返回默认注册表（含集群采集巡检任务）。"""
    registry = TaskRegistry()

    # 延迟导入避免循环依赖
    from server.engine.cluster import collect_cluster_status
    from server.engine.observer import run_observer

    registry.register(ScheduledTask(
        name="cluster-collect",
        task_type=TASK_TYPE_READONLY,
        run=collect_cluster_status,
    ))

    registry.register(ScheduledTask(
        name="loop-observer",
        task_type=TASK_TYPE_READONLY,
        run=run_observer,
    ))

    return registry


if __name__ == "__main__":
    sys.exit(main())

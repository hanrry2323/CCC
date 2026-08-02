"""Engine 主入口 — 配置加载 + 主循环（薄驱动，只做编排，不真拉执行体）。

用法：
    $PYTHON_BIN -m server.engine.main --config <config.env>        # 持续模式（循环 + 心跳）
    $PYTHON_BIN -m server.engine.main --config <config.env> --once  # 单次扫描 + 收单后退出

`--once` 输出一行 JSON 统计；缺 `--config` 或配置缺失 → 非零退出并报错。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Any

from server.config.loader import ConfigError, load_config
from server.engine.dispatch import (
    DispatchDecision,
    ExecutorRegistry,
    decide,
    load_registry,
)
from server.engine.store import BoardStore, InMemoryBoardStore
from server.engine.task import State

logger = logging.getLogger("ccc.engine")

DEFAULT_HEARTBEAT_SECONDS = 60


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ccc-engine",
        description="CCC Engine 薄驱动核心（只做编排，T4 前不真拉执行体）",
    )
    parser.add_argument("--config", required=True, help="config.env 路径（必填）")
    parser.add_argument("--once", action="store_true", help="单次扫描 + 收单后退出")
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=DEFAULT_HEARTBEAT_SECONDS,
        help="持续模式心跳间隔（秒）",
    )
    return parser.parse_args(argv)


def run_once(registry: ExecutorRegistry, store: BoardStore) -> dict[str, int]:
    """单次扫描 + 派发 + 收单（T2 占位）。

    1. 扫描「待分派」work；
    2. 按注册表决策派发：可后台 CLI → 写「模拟拉起」日志；手动 GUI → 挂起等人；
       管理席/验收席/未知角色 → 不派发；
    3. 收单：无真实执行结果（T4 前），仅统计在飞数量。
    """
    pending = store.list_work(state=State.TODO)
    dispatched = 0
    for work in pending:
        decision = decide(work.role, registry)
        if decision is DispatchDecision.AUTO:
            logger.info(
                "模拟拉起执行体（T4 前不真拉）: work=%s role=%s", work.id, work.role
            )
            work.transition(State.RUNNING)
            store.save_work(work)
            dispatched += 1
        elif decision is DispatchDecision.MANUAL:
            logger.info("挂起等人接单: work=%s role=%s", work.id, work.role)
            work.transition(State.RUNNING)
            store.save_work(work)
            dispatched += 1
        else:
            logger.warning("不参与派发: work=%s role=%s", work.id, work.role)
    in_flight = len(store.list_work(state=State.RUNNING))
    collected = 0  # 无真实执行结果（T4 前）
    return {
        "mode": "once",
        "scanned": len(pending),
        "dispatched": dispatched,
        "in_flight": in_flight,
        "collected": collected,
    }


def run_loop(
    registry: ExecutorRegistry,
    store: BoardStore,
    heartbeat_interval: int,
) -> None:
    """持续模式：每轮扫描 + 收单，心跳占位。"""
    logger.info("Engine 持续模式启动（T4 前不真拉执行体）")
    while True:
        summary = run_once(registry, store)
        logger.info("heartbeat: %s", json.dumps(summary, ensure_ascii=False))
        time.sleep(heartbeat_interval)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    try:
        cfg: dict[str, Any] = load_config(args.config)
        registry_path = cfg.get("EXECUTOR_REGISTRY_PATH", "")
        if not registry_path:
            print("[FATAL] EXECUTOR_REGISTRY_PATH 未配置", file=sys.stderr)
            return 2
        registry = load_registry(registry_path)
    except (ConfigError, OSError, ValueError) as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 2

    store: BoardStore = InMemoryBoardStore()
    if args.once:
        summary = run_once(registry, store)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    run_loop(registry, store, args.heartbeat_interval)
    return 0  # 持续模式不返回（Ctrl-C 终止）


if __name__ == "__main__":
    sys.exit(main())

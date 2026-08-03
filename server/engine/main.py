"""Engine 主入口 — 配置加载 + 主循环（薄驱动，负责真实派发/收单）。

用法：
    $PYTHON_BIN -m server.engine.main --config <config.env>        # 持续模式（循环 + 心跳）
    $PYTHON_BIN -m server.engine.main --config <config.env> --once  # 单次扫描 + 派发 + 收单后退出

`--once` 输出一行 JSON 统计；缺 `--config` 或配置缺失 → 非零退出并报错。

Engine 职责（契约 §2/§7）：读取执行体注册表 → 派发（可后台 CLI 自动拉起 / 手动 GUI 挂起）→
收单（按退出码 + 输出判定）→ 状态机流转（待分派 → 执行中 → 已回写/打回 → 已关闭）。

派发管道（T32 真实派发闭环）：
1. decide(role) → AUTO：从注册表取 CLI 条目，build_command 生成 argv；
2. subprocess.Popen 启动，stdout/stderr 重定向到 {EXECUTOR_LOG_DIR}/{work_id}.log；
3. wait(timeout=EXECUTOR_TIMEOUT_SECONDS)；
4. 退出码 0 → 已回写；非 0 / 超时 / 启动失败 → 打回（附问题清单）。
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from server.config.loader import ConfigError, load_config
from server.engine.dispatch import (
    DispatchDecision,
    ExecutorRegistry,
    build_command,
    decide,
    load_registry,
)
from server.engine.store import BoardStore, FileBoardStore
from server.engine.task import State, Work

logger = logging.getLogger("ccc.engine")

DEFAULT_HEARTBEAT_SECONDS = 60
DEFAULT_EXECUTOR_TIMEOUT = 300


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ccc-engine",
        description="CCC Engine 薄驱动核心（负责真实派发/收单）",
    )
    parser.add_argument("--config", required=True, help="config.env 路径（必填）")
    parser.add_argument("--once", action="store_true", help="单次扫描 + 派发 + 收单后退出")
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=DEFAULT_HEARTBEAT_SECONDS,
        help="持续模式心跳间隔（秒）",
    )
    return parser.parse_args(argv)


def _dispatch_and_collect(
    work: Work,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
) -> tuple[bool, list[str]]:
    """真实派发单个 work + 同步收单。

    Returns:
        (ok, problems)：ok=True → 已回写；ok=False → 打回（附问题清单）。
    """
    entry = registry.cli_entry_for_role(work.role)
    if entry is None:
        return False, [f"角色 {work.role} 无可后台 CLI 注册行"]

    default_workdir = cfg.get("DATA_DIR", "")
    try:
        cmd = build_command(
            entry,
            work_id=work.id,
            role=work.role,
            card_path=work.card_path,
            default_workdir=default_workdir,
        )
    except ValueError as exc:
        return False, [f"命令构造失败: {exc}"]

    log_path = log_dir / f"{work.id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("拉起执行体: work=%s role=%s cmd=%s log=%s", work.id, work.role, cmd, log_path)

    try:
        with log_path.open("w", encoding="utf-8") as logf:
            proc = subprocess.Popen(  # noqa: S603 - 命令来自注册表配置，非用户输入
                cmd,
                stdout=logf,
                stderr=subprocess.STDOUT,
                cwd=entry.workdir or default_workdir or None,
            )
    except FileNotFoundError as exc:
        return False, [f"启动失败（命令不存在）: {exc}"]
    except OSError as exc:
        return False, [f"启动失败: {exc}"]

    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return False, [f"执行超时（{timeout}s 已 kill）"]

    if returncode == 0:
        return True, []
    return False, [f"退出码非 0: {returncode}（日志: {log_path}）"]


def run_once(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any] | None = None,
) -> dict[str, int]:
    """单次扫描 + 派发 + 收单。

    1. 扫描「待分派」work；
    2. 按注册表决策派发：可后台 CLI → 真实拉起执行体 + 同步收单；手动 GUI → 挂起等人；
       管理席/验收席/未知角色 → 不派发；
    3. 收单：按退出码 + 输出判定 → 状态机流转（执行中 → 已回写/打回）。
    """
    cfg = cfg or {}
    timeout = int(cfg.get("EXECUTOR_TIMEOUT_SECONDS") or DEFAULT_EXECUTOR_TIMEOUT)
    log_dir_str = cfg.get("EXECUTOR_LOG_DIR", "").strip()
    if not log_dir_str:
        raise ConfigError("EXECUTOR_LOG_DIR 未配置（必填，执行体日志目录）")
    log_dir = Path(log_dir_str)
    default_workdir = cfg.get("DATA_DIR", "")

    pending = store.list_work(state=State.TODO)
    dispatched = 0
    collected = 0
    timed_out = 0
    for work in pending:
        decision = decide(work.role, registry)
        if decision is DispatchDecision.AUTO:
            work.transition(State.RUNNING)
            store.save_work(work)
            dispatched += 1
            ok, problems = _dispatch_and_collect(work, registry, cfg, log_dir, timeout)
            if ok:
                work.transition(State.DONE)
                store.save_work(work)
                collected += 1
                logger.info("收单成功: work=%s → 已回写", work.id)
            else:
                if any("超时" in p for p in problems):
                    timed_out += 1
                work.transition(State.REJECTED, problems=problems)
                store.save_work(work)
                logger.warning("收单失败: work=%s → 打回 %s", work.id, problems)
        elif decision is DispatchDecision.MANUAL:
            logger.info("挂起等人接单: work=%s role=%s", work.id, work.role)
            work.transition(State.RUNNING)
            store.save_work(work)
            dispatched += 1
        else:
            logger.warning("不参与派发: work=%s role=%s", work.id, work.role)

    in_flight = len(store.list_work(state=State.RUNNING))
    summary: dict[str, int] = {
        "mode": "once",
        "scanned": len(pending),
        "dispatched": dispatched,
        "in_flight": in_flight,
        "collected": collected,
        "timed_out": timed_out,
    }
    return summary


def run_loop(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any],
    heartbeat_interval: int,
) -> None:
    """持续模式：每轮扫描 + 派发 + 收单，心跳 + 催单日志（超时未回写任务）。"""
    logger.info("Engine 持续模式启动（真实派发/收单）")
    while True:
        summary = run_once(registry, store, cfg)
        logger.info("heartbeat: %s", json.dumps(summary, ensure_ascii=False))
        if summary["timed_out"] > 0:
            logger.warning("催单: 本轮 %d 个任务超时未回写", summary["timed_out"])
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

    dispatch_dir = cfg.get("DISPATCH_DIR") or "docs/dispatch"
    store: BoardStore = FileBoardStore(dispatch_dir, registry)
    if args.once:
        summary = run_once(registry, store, cfg)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    run_loop(registry, store, cfg, args.heartbeat_interval)
    return 0  # 持续模式不返回（Ctrl-C 终止）


if __name__ == "__main__":
    sys.exit(main())

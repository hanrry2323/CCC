#!/usr/bin/env python3
"""ccc-engine.py — CCC 串行执行引擎 (v0.20.1)

替代 7 角色 launchd 定时轮询模式。
一个常驻守护进程，按 task 级别串行驱动 backlog→released 全链路。

使用方式:
  python3 ccc-engine.py                              # CCC 自身
  python3 ccc-engine.py --workspace ~/program/qxo     # qxo 项目

退出:
  Ctrl+C 或 SIGTERM → 优雅关闭
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 确保当前目录在 path 中
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from _config import Config
from _board_store import FileBoardStore

# ccc-board.py 含连字符，用 importlib 加载
import importlib.util as _importlib_util
_ccc_board_path = str(_script_dir / "ccc-board.py")
_spec = _importlib_util.spec_from_file_location("ccc_board", _ccc_board_path)
ccc_board = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(ccc_board)

# 别名
dev_role_launch = ccc_board.dev_role_launch
dev_role_relaunch = ccc_board.dev_role_relaunch
dev_role_check_complete = ccc_board.dev_role_check_complete
reviewer_role = ccc_board.reviewer_role
tester_role = ccc_board.tester_role
kb_role = ccc_board.kb_role
list_tasks = ccc_board.list_tasks
update_index = ccc_board.update_index
MAX_RETRY = ccc_board.MAX_RETRY

cfg = Config()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def engine_log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[engine {ts}] {msg}", flush=True)


def engine_loop(workspace: str) -> None:
    """引擎主循环：串行驱动 task backlog→released"""

    engine_log(f"CCC Engine 启动 (workspace={workspace})")
    engine_log(f"  poll_interval={cfg.engine_poll_interval}s, idle_sleep={cfg.engine_idle_sleep}s")
    engine_log(f"  max_retry={MAX_RETRY}")

    running_task_id: str | None = None  # 当前正在执行的 task
    iteration = 0

    # ── 启动扫描：检查已有的 in_progress 任务 ──
    in_prog = list_tasks("in_progress")
    if in_prog:
        running_task_id = in_prog[-1]["id"]
        engine_log(f"发现已有 in_progress 任务: {running_task_id}")

    while True:
        iteration += 1
        tick_start = time.time()

        try:
            # ── Step 1: 有正在执行的 task？──
            if running_task_id:
                result = dev_role_check_complete(running_task_id)
                status = result.get("status", "unknown")

                if status == "running":
                    # 仍执行中，等下次轮询
                    _write_heartbeat(workspace, running_task_id)
                    if iteration % 60 == 0:  # 每 60 轮打印一次（约 10min）
                        engine_log(f"{running_task_id} 执行中")

                elif status == "success":
                    engine_log(f"{running_task_id} → testing, 立即跑 reviewer+tester")
                    # 串行运行 reviewer + tester
                    reviewer_role()
                    tester_role()

                    # 检查是否都进了 verified
                    verified = list_tasks("verified")
                    if any(t["id"] == running_task_id for t in verified):
                        engine_log(f"{running_task_id} → verified, 立即 kb")
                        kb_role()
                        engine_log(f"{running_task_id} 全链路完成")
                    else:
                        engine_log(f"{running_task_id} reviewer/tester 未通过")

                    update_index()
                    running_task_id = None
                    continue  # 立即检查下一个 task

                elif status == "failed":
                    retry = result.get("retry", 0)
                    engine_log(f"{running_task_id} 失败 (retry={retry}), 重新启动")
                    # 重新启动（task 在 in_progress，用 relaunch）
                    dev_role_relaunch(running_task_id)
                    # 等下次轮询
                    _wait_tick(tick_start)
                    continue

                elif status == "quarantined":
                    engine_log(f"{running_task_id} 重试耗尽, 已隔离, 移向下一个")
                    update_index()
                    running_task_id = None
                    continue  # 立即检查下一个

                else:
                    # not_found 或其他异常：task 不在 in_progress 了
                    if status == "not_found":
                        engine_log(f"{running_task_id} 不在 in_progress (可能已被外部移走)")
                    else:
                        engine_log(f"{running_task_id} 未知状态: {status}")
                    running_task_id = None
                    continue

            # ── Step 2: 没有活跃 task，取 planned ──
            if running_task_id is None:
                planned = list_tasks("planned")
                # 找第一个有 plan+phases 的 task
                for task in planned:
                    tid = task["id"]
                    plan_file = cfg.workspace / ".ccc" / "plans" / f"{tid}.plan.md"
                    phases_file = cfg.workspace / ".ccc" / "phases" / f"{tid}.phases.json"
                    if plan_file.exists() and phases_file.exists():
                        running_task_id = tid
                        engine_log(f"取新 task: {tid}")
                        launch_r = dev_role_launch(tid)
                        if "error" in launch_r:
                            engine_log(f"启动 {tid} 失败: {launch_r['error']}")
                            running_task_id = None
                            continue  # 试下一个
                        break  # 启动了一个, 等下次轮询

                if running_task_id is None:
                    # 彻底无事可做
                    _check_stale()
                    _write_heartbeat(workspace, None)
                    time.sleep(cfg.engine_idle_sleep)
                    continue

        except KeyboardInterrupt:
            engine_log("收到 SIGINT, 优雅关闭")
            break
        except Exception as e:
            engine_log(f"异常: {e}")
            # 防止 panic 退出
            time.sleep(cfg.engine_idle_sleep)
            continue

        _wait_tick(tick_start)


def _wait_tick(tick_start: float) -> None:
    """等够 poll_interval（活跃时短等，不阻塞 CPU）"""
    elapsed = time.time() - tick_start
    remaining = cfg.engine_poll_interval - elapsed
    if remaining > 0:
        time.sleep(min(remaining, cfg.engine_poll_interval))


def _check_stale() -> None:
    """空闲时检查 stale in_progress 任务"""
    from datetime import datetime as _dt
    now = _dt.now(timezone.utc)
    for task in list_tasks("in_progress"):
        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            hours_stale = (now - updated).total_seconds() / 3600
            if hours_stale > cfg.max_stale_hours:
                # 移入异常
                store = FileBoardStore(cfg.workspace)
                store.quarantine(
                    task["id"],
                    f"engine: in_progress 滞留 {hours_stale:.1f}h (阈值 {cfg.max_stale_hours}h)"
                )
                engine_log(f"stale: {task['id']} in_progress 滞留 {hours_stale:.1f}h → abnormal")
        except (ValueError, TypeError):
            pass


def _write_heartbeat(workspace: str, running_task_id: str | None) -> None:
    """写心跳到 .ccc/engine-heartbeat.json"""
    hb = {
        "workspace": workspace,
        "running": running_task_id or None,
        "timestamp": now_iso(),
    }
    hb_file = cfg.workspace / ".ccc" / "engine-heartbeat.json"
    try:
        hb_file.write_text(json.dumps(hb, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser(description="CCC Engine — 串行执行守护进程")
    ap.add_argument("--workspace", default=str(cfg.workspace), help="目标 workspace 路径")
    args = ap.parse_args()

    ws = Path(args.workspace).resolve()
    if not (ws / ".ccc" / "board").exists():
        print(f"[engine] 错误: {ws} 没有 .ccc/board/ 目录", file=sys.stderr)
        sys.exit(1)

    # 覆盖 workspace
    os.environ["CCC_WORKSPACE"] = str(ws)

    # 优雅关闭信号
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    try:
        engine_loop(str(ws))
    except KeyboardInterrupt:
        engine_log("Engine 关闭")
        sys.exit(0)


if __name__ == "__main__":
    main()

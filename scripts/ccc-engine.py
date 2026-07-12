#!/usr/bin/env python3
"""ccc-engine.py — CCC 并行执行引擎 (v0.20.1+, v0.28.1 起最多 3 task 并发)

替代 7 角色 launchd 定时轮询模式。
一个常驻守护进程，驱动 backlog→released 全链路（同 workspace 最多 MAX_CONCURRENT 个 task 并行）。

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

from _config import Config, get_logger
from _board_store import FileBoardStore
from _utils import now_iso as _utils_now_iso

_log = get_logger("engine")

# 必须在加载 ccc-board.py 前从 --workspace 参数设置环境变量，
# 因为 ccc-board.py 模块级代码会立即初始化 Config() 读取 CCC_WORKSPACE
import sys as _sys
for _i, _arg in enumerate(_sys.argv):
    if _arg == "--workspace" and _i + 1 < len(_sys.argv):
        os.environ["CCC_WORKSPACE"] = _sys.argv[_i + 1]
        break

# ccc-board.py 含连字符，无法用 `import ccc-board` 标准 import。
# 评估过的替代方案：
#   1. 改名为 ccc_board.py — 风险高（launchd plist / 文档 / 已发布 skill 引用 ccc-board.py）
#   2. 创建 ccc_board.py symlink — 维护负担
#   3. 改用 importlib（当前）— 启动开销 ~5ms，可接受
# v0.28.0 (L-002): 保留方案 3，加注释说明决策原因。
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
move_task = ccc_board.move_task
update_index = ccc_board.update_index
MAX_RETRY = ccc_board.MAX_RETRY

# v0.24: phase 依赖解析
_load_phases = ccc_board._load_phases
_resolve_phase_dependencies = ccc_board._resolve_phase_dependencies
_apply_phase_status_updates = ccc_board._apply_phase_status_updates
_task_all_phases_terminal = ccc_board._task_all_phases_terminal
_check_phase_failures = ccc_board._check_phase_failures
_current_running_phase = ccc_board._current_running_phase

cfg = Config()


def now_iso() -> str:
    """v0.28.1: 委托 _utils（北京时间 +08:00）。"""
    return _utils_now_iso()


def engine_log(msg: str) -> None:
    """v0.28.0 (R-08): 改用统一 logger 替代 print。"""
    _log.info("%s", msg)


_engine_shutdown = False  # SIGTERM 标志

# v0.28.0 (F1-C1 修): product_role 失败重试上限
# product_role 是轻量级 prompt（plan 生成），短时重试 3 次即止损
_MAX_PRODUCT_RETRIES = 3

# 与 opencode-pool.py MAX_PARALLEL 一致
MAX_CONCURRENT = 3

# v0.28.0 (X-H1 修): 缓存 FileBoardStore 实例，避免每次调用重新构造
_store_instance: FileBoardStore | None = None


def _get_store(workspace: str | Path) -> FileBoardStore:
    """返回缓存的 FileBoardStore 实例（惰性初始化）"""
    global _store_instance
    if _store_instance is None:
        _store_instance = FileBoardStore(Path(workspace) if isinstance(workspace, str) else workspace)
    return _store_instance


def engine_loop(workspace: str) -> None:
    """引擎主循环：并行驱动 task backlog→released（最多 MAX_CONCURRENT 个）"""
    global _engine_shutdown

    engine_log(f"CCC Engine 启动 (workspace={workspace})")
    engine_log(f"  poll_interval={cfg.engine_poll_interval}s, idle_sleep={cfg.engine_idle_sleep}s")
    engine_log(f"  max_retry={MAX_RETRY}, max_concurrent={MAX_CONCURRENT}")

    active_tasks: dict[str, dict] = {}  # task_id -> {"complexity": ..., "started_at": ...}
    iteration = 0

    def _handle_task_result(tid: str, result: dict, complexity: str) -> bool:
        """处理 dev_role_check_complete 结果。返回 True 表示从 active_tasks 移除。"""
        status = result.get("status", "unknown")

        if status == "success":
            if complexity == "small":
                engine_log(f"{tid} complexity=small, 跳过 reviewer+tester → 直通 kb")
                move_task(tid, "in_progress", "testing")
                move_task(tid, "testing", "verified")
                verified = list_tasks("verified")
                if any(t["id"] == tid for t in verified):
                    engine_log(f"{tid} → verified, 立即 kb")
                    kb_role()
                    try:
                        auto_r = ccc_board.auto_approve_agents()
                        if auto_r.get("approved", 0) > 0:
                            engine_log(f"auto-approve-agents ✓ {auto_r['approved']} 条建议")
                    except Exception as exc:
                        engine_log(f"auto_approve_agents 异常: {exc}")
                    engine_log(f"{tid} 全链路完成 (small path)")
                else:
                    engine_log(f"{tid} small path: 移入 verified 失败")
                update_index()
                return True

            engine_log(f"{tid} → testing, 立即跑 reviewer+tester")
            reviewer_role()
            tester_role()

            verified = list_tasks("verified")
            if any(t["id"] == tid for t in verified):
                engine_log(f"{tid} → verified, 立即 kb")
                kb_role()
                try:
                    auto_r = ccc_board.auto_approve_agents()
                    if auto_r.get("approved", 0) > 0:
                        engine_log(
                            f"auto-approve-agents ✓ {auto_r['approved']} 条建议合入 AGENTS.md"
                        )
                except Exception as exc:
                    engine_log(f"auto_approve_agents 异常: {exc}")
                engine_log(f"{tid} 全链路完成")
            else:
                engine_log(f"{tid} reviewer/tester 未通过")

            update_index()
            return True

        if status == "failed":
            retry = result.get("retry", 0)
            failure_summary = _check_phase_failures(tid)
            if failure_summary.get("all_failed_or_skipped"):
                engine_log(
                    f"{tid} 所有 phase failed/skipped "
                    f"(skipped={failure_summary.get('skipped')})"
                )
                update_index()
                return True
            cur = _current_running_phase(tid)
            engine_log(f"{tid} 失败 (retry={retry}), relaunch phase {cur}")
            dev_role_relaunch(tid)
            return False

        if status == "quarantined":
            failure_summary = _check_phase_failures(tid)
            if failure_summary.get("all_failed_or_skipped"):
                engine_log(
                    f"{tid} 所有 phase failed/skipped → abnormal "
                    f"(skipped_downstream={failure_summary['skipped']})"
                )
            else:
                engine_log(f"{tid} 重试耗尽, 已隔离, 移向下一个")
            update_index()
            return True

        if status == "not_found":
            engine_log(f"{tid} 不在 in_progress (可能已被外部移走)")
        else:
            engine_log(f"{tid} 未知状态: {status}")
        return True

    # ── 启动扫描：检查已有的 in_progress 任务 ──
    in_prog = list_tasks("in_progress")
    if in_prog:
        engine_log(f"发现 {len(in_prog)} 个 in_progress 任务，恢复检查")
    for task in in_prog:
        tid = task["id"]
        complexity = task.get("complexity", "medium")
        result = dev_role_check_complete(tid)
        status = result.get("status", "unknown")
        if status == "running":
            active_tasks[tid] = {"complexity": complexity, "started_at": now_iso()}
            engine_log(f"{tid} 检查 PID 存活")
        elif status in ("success", "failed"):
            engine_log(f"{tid} 已完成 (status={status}), 继续链")
            if not _handle_task_result(tid, result, complexity):
                active_tasks[tid] = {"complexity": complexity, "started_at": now_iso()}
        elif status == "quarantined":
            _handle_task_result(tid, result, complexity)
        else:
            _handle_task_result(tid, result, complexity)

    while True:
        if _engine_shutdown:
            engine_log("收到关闭信号，停止接收新任务")
            break
        iteration += 1
        tick_start = time.time()

        try:
            # ── Step 1: 检查所有活跃 task 的完成状态 ──
            completed_tasks: list[str] = []
            if active_tasks:
                for tid, info in list(active_tasks.items()):
                    result = dev_role_check_complete(tid)
                    status = result.get("status", "unknown")
                    complexity = info.get("complexity", "medium")

                    if status == "running":
                        if iteration % 60 == 0:
                            engine_log(f"{tid} 执行中")
                        continue

                    if _handle_task_result(tid, result, complexity):
                        completed_tasks.append(tid)

                for tid in completed_tasks:
                    active_tasks.pop(tid, None)

                running_ids = list(active_tasks.keys())
                if running_ids:
                    _write_heartbeat(workspace, running_ids[0])

            # ── Step 1.5 + Step 2: 池有空位时消费 backlog / 取 planned ──
            while len(active_tasks) < MAX_CONCURRENT and not _engine_shutdown:
                # ── Step 1.5 (v0.28.0 F-1): backlog 自动消费 ──
                backlog = ccc_board.list_tasks("backlog")
                if backlog:
                    tid = backlog[0]["id"]
                    fail_counter_dir = cfg.workspace / ".ccc" / ".product-fail-counter"
                    fail_counter_path = fail_counter_dir / f"{tid}.json"

                    fail_count = 0
                    if fail_counter_path.exists():
                        try:
                            fail_data = json.loads(fail_counter_path.read_text())
                            fail_count = fail_data.get("fail_count", 0)
                        except (json.JSONDecodeError, OSError):
                            fail_count = 0

                    if fail_count >= _MAX_PRODUCT_RETRIES:
                        engine_log(
                            f"{tid} 已失败 {fail_count} 次 >= {_MAX_PRODUCT_RETRIES}，"
                            f"移入 abnormal"
                        )
                        store = _get_store(cfg.workspace)
                        store.quarantine(
                            tid,
                            f"product_role 连续失败 {fail_count} 次",
                        )
                        continue

                    engine_log(
                        f"backlog 自动拆分: {tid} (此前失败 {fail_count} 次)"
                    )
                    try:
                        ccc_board.product_role(task_id=tid)
                        if fail_counter_path.exists():
                            fail_counter_path.unlink()
                    except Exception as exc:
                        fail_count += 1
                        fail_counter_dir.mkdir(parents=True, exist_ok=True)
                        fail_counter_path.write_text(
                            json.dumps({"fail_count": fail_count}, indent=2)
                        )
                        engine_log(
                            f"product_role({tid}) 异常: {exc} (失败 #{fail_count})"
                        )
                        if fail_count >= _MAX_PRODUCT_RETRIES:
                            engine_log(
                                f"{tid} 失败 {fail_count} 次 >= "
                                f"{_MAX_PRODUCT_RETRIES}，移入 abnormal"
                            )
                            store = _get_store(cfg.workspace)
                            store.quarantine(
                                tid,
                                f"product_role 连续失败 {fail_count} 次",
                            )
                    continue

                # ── Step 2: 从 planned 取新 task ──
                planned = list_tasks("planned")
                launched = False
                for task in planned:
                    tid = task["id"]
                    if tid in active_tasks:
                        continue
                    plan_file = cfg.workspace / ".ccc" / "plans" / f"{tid}.plan.md"
                    phases_file = cfg.workspace / ".ccc" / "phases" / f"{tid}.phases.json"
                    if plan_file.exists() and phases_file.exists():
                        phases = _load_phases(tid)
                        if phases:
                            executable, blocked, skipped = _resolve_phase_dependencies(phases)
                            if blocked or skipped:
                                _apply_phase_status_updates(tid, blocked, skipped)
                                engine_log(
                                    f"{tid} phase 依赖解析: executable={sorted(executable)} "
                                    f"blocked={sorted(blocked)} skipped={sorted(skipped)}"
                                )
                            if phases and all(
                                p.get("status") in ("skipped", "failed") or
                                (p.get("phase") in skipped)
                                for p in phases
                            ):
                                engine_log(
                                    f"{tid} 所有 phase 被跳过（依赖失败链），跳过 task 启动"
                                )
                                continue

                        complexity = task.get("complexity", "medium")
                        engine_log(f"取新 task: {tid} (complexity={complexity})")
                        launch_r = dev_role_launch(tid)
                        if "error" in launch_r:
                            engine_log(f"启动 {tid} 失败: {launch_r['error']}")
                            continue
                        active_tasks[tid] = {
                            "complexity": complexity,
                            "started_at": now_iso(),
                        }
                        update_index()
                        launched = True
                        break

                if not launched:
                    break

            if not active_tasks:
                _check_stale()
                _write_heartbeat(workspace, None)

                if _audit_should_run(workspace):
                    engine_log("触发 audit_role（全项目扫描）")
                    try:
                        ccc_board.audit_role(workspace=workspace)
                    except Exception as exc:
                        engine_log(f"audit_role 异常: {exc}")

                _check_new_reviews()

                time.sleep(cfg.engine_idle_sleep)
                continue

        except KeyboardInterrupt:
            engine_log("收到 SIGINT, 优雅关闭")
            break
        except Exception as e:
            import traceback as _tb
            engine_log(f"异常: {e}")
            engine_log(f"  {_tb.format_exc().splitlines()[-2]}")
            time.sleep(cfg.engine_idle_sleep)
            continue

        _wait_tick(tick_start)


def _wait_tick(tick_start: float) -> None:
    """等够 poll_interval（活跃时短等，不阻塞 CPU）"""
    elapsed = time.time() - tick_start
    remaining = cfg.engine_poll_interval - elapsed
    if remaining > 0:
        time.sleep(min(remaining, cfg.engine_poll_interval))


def _audit_should_run(workspace: str, interval_hours: int = 2) -> bool:
    """检查是否该跑 audit：距上次跑 ≥ interval_hours

    G11: 每个 workspace 独立 last_run 文件，避免 5 个 engine 实例共享同一文件
    用 workspace 目录名（最后一段）做 slug，不用完整路径
    """
    from datetime import datetime as _dt
    ws_slug = Path(workspace).name if workspace else "CCC"
    last_run_file = Path.home() / ".ccc" / f"audit-last-run.{ws_slug}.json"
    # fallback: 兼容旧版无 slug 文件
    if not last_run_file.exists():
        old_file = Path.home() / ".ccc" / "audit-last-run.json"
        if old_file.exists():
            return _audit_check_old(old_file, interval_hours)
        return True
    try:
        data = json.loads(last_run_file.read_text())
        last = _dt.fromisoformat(data["last_run"].replace("Z", "+00:00"))
        now = _dt.now(timezone.utc)
        hours = (now - last).total_seconds() / 3600
        return hours >= interval_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def _audit_check_old(old_file, interval_hours: int = 2) -> bool:
    """检查旧版 audit-last-run.json（无 workspace slug）"""
    from datetime import datetime as _dt
    try:
        data = json.loads(old_file.read_text())
        last = _dt.fromisoformat(data["last_run"].replace("Z", "+00:00"))
        now = _dt.now(timezone.utc)
        hours = (now - last).total_seconds() / 3600
        return hours >= interval_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def _check_new_reviews() -> None:
    """检查 .ccc/reviews/ 下新报告格式（v0.23.4 流程加固）"""
    try:
        from _review_validator import scan_review_dir
        results = scan_review_dir(str(cfg.workspace))
        for r in results:
            if not r.get("valid"):
                fname = Path(r.get("file", "?")).name
                errs = "; ".join(r["errors"][:3])
                engine_log(f"🔴 报告格式错误 {fname}: {errs}")
    except ImportError as e:
        _log.warning("_review_validator unavailable, skipping review scan: %s", e)
    except Exception as exc:
        engine_log(f"review 校验异常: {exc}")


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
                store = _get_store(cfg.workspace)
                store.quarantine(
                    task["id"],
                    f"engine: in_progress 滞留 {hours_stale:.1f}h (阈值 {cfg.max_stale_hours}h)"
                )
                engine_log(f"stale: {task['id']} in_progress 滞留 {hours_stale:.1f}h → abnormal")
        except (ValueError, TypeError) as e:
            _log.warning("stale task timestamp parse failed for %s: %s", task.get("id"), e)
    try:
        store = _get_store(cfg.workspace)
        store.cleanup_events(max_days=30)
    except Exception as e:
        _log.warning("events TTL cleanup failed: %s", e, exc_info=True)
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
    except OSError as e:
        _log.warning("engine heartbeat write failed: %s", e)


def main():
    ap = argparse.ArgumentParser(description="CCC Engine — 串行执行守护进程")
    ap.add_argument("--workspace", default=str(cfg.workspace), help="目标 workspace 路径")
    args = ap.parse_args()

    ws = Path(args.workspace).resolve()
    if not (ws / ".ccc" / "board").exists():
        _log.error("[engine] 错误: %s 没有 .ccc/board/ 目录", ws)
        sys.exit(1)

    os.environ["CCC_WORKSPACE"] = str(ws)

    def _handle_sigterm(signum, frame):
        global _engine_shutdown
        if _engine_shutdown:
            return
        _engine_shutdown = True
        engine_log("收到 SIGTERM, 优雅关闭中...")

    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        engine_loop(str(ws))
    except KeyboardInterrupt:
        engine_log("Engine 关闭")
    except SystemExit:
        _log.debug("engine exiting via SystemExit")
    if _engine_shutdown:
        remaining = 10
        while remaining > 0:
            time.sleep(1)
            remaining -= 1
        engine_log("Engine 终止")
    else:
        engine_log("Engine 正常退出")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

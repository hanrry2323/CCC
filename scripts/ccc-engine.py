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
from _logger import get_logger
from _utils import now_iso as _utils_now_iso

_log = get_logger("engine")

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
update_index = ccc_board.update_index
MAX_RETRY = ccc_board.MAX_RETRY

# v0.24: phase 依赖解析
_load_phases = ccc_board._load_phases
_resolve_phase_dependencies = ccc_board._resolve_phase_dependencies
_apply_phase_status_updates = ccc_board._apply_phase_status_updates
_task_all_phases_terminal = ccc_board._task_all_phases_terminal

cfg = Config()


def now_iso() -> str:
    """v0.28.0 (H-003): 委托 _utils 统一实现。"""
    return _utils_now_iso()


def engine_log(msg: str) -> None:
    """v0.28.0 (R-08): 改用统一 logger 替代 print。"""
    _log.info("%s", msg)


_engine_shutdown = False  # SIGTERM 标志

# v0.28.0 (F1-C1 修): product_role 失败重试上限
# product_role 是轻量级 prompt（plan 生成），短时重试 3 次即止损
_MAX_PRODUCT_RETRIES = 3

# v0.28.0 (X-H1 修): 缓存 FileBoardStore 实例，避免每次调用重新构造
_store_instance: FileBoardStore | None = None


def _get_store(workspace: str | Path) -> FileBoardStore:
    """返回缓存的 FileBoardStore 实例（惰性初始化）"""
    global _store_instance
    if _store_instance is None:
        _store_instance = FileBoardStore(Path(workspace) if isinstance(workspace, str) else workspace)
    return _store_instance


def engine_loop(workspace: str) -> None:
    """引擎主循环：串行驱动 task backlog→released"""
    global _engine_shutdown

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
        # G4: 立即检查 task 是否真的在运行，.pid 进程不存在则重启
        result = dev_role_check_complete(running_task_id)
        if result.get("status") == "running":
            # 检查 PID 是否存活
            engine_log(f"{running_task_id} 检查 PID 存活")
        elif result.get("status") in ("success", "failed"):
            engine_log(f"{running_task_id} 已完成 (status={result.get('status')}), 继续链")
            running_task_id = None  # 让主循环从 planned 取下一个

    while True:
        if _engine_shutdown:
            engine_log("收到关闭信号，停止接收新任务")
            break
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
                        # v0.28.0 (F-4): kb_role 后自动 approve-agents（7 天冷却 + 重复检测）
                        # 替代原 100% 人工审批；保留原 approve_agents 函数供手工触发
                        try:
                            auto_r = ccc_board.auto_approve_agents()
                            if auto_r.get("approved", 0) > 0:
                                engine_log(
                                    f"auto-approve-agents ✓ {auto_r['approved']} 条建议合入 AGENTS.md"
                                )
                        except Exception as exc:
                            engine_log(f"auto_approve_agents 异常: {exc}")
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
                    # v0.24: 跑失败传染 + 决定 task 是 quarantined 还是 abnormal
                    failure_summary = _check_phase_failures(running_task_id)
                    if failure_summary.get("all_failed_or_skipped"):
                        engine_log(
                            f"{running_task_id} 所有 phase failed/skipped → abnormal "
                            f"(skipped_downstream={failure_summary['skipped']})"
                        )
                    else:
                        engine_log(
                            f"{running_task_id} 重试耗尽, 已隔离, 移向下一个"
                        )
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

            # ── Step 1.5 (v0.28.0 F-1): backlog 自动消费 ──
            # 老板"我给你任务你来拆"的核心断点：engine idle 时如果 backlog 非空，
            # 自动调 product_role 拆分（生成 plan + phases）→ 挪 planned。
            # 断点已修：现在 user 只需 `create_task` 落 backlog，engine 自动消费。
            # v0.28.0 (F1-C1 修): 失败计数器 — 连续 _MAX_PRODUCT_RETRIES 次失败移入 abnormal
            if running_task_id is None:
                backlog = ccc_board.list_tasks("backlog")
                if backlog:
                    tid = backlog[0]["id"]
                    fail_counter_dir = cfg.workspace / ".ccc" / ".product-fail-counter"
                    fail_counter_path = fail_counter_dir / f"{tid}.json"

                    # 读当前失败计数
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
                        # 成功：清除失败计数
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
                    continue  # 立即重检（消费下一个或进 planned）

            # ── Step 2: 没有活跃 task，取 planned ──
            if running_task_id is None:
                planned = list_tasks("planned")
                # 找第一个有 plan+phases 的 task
                for task in planned:
                    tid = task["id"]
                    plan_file = cfg.workspace / ".ccc" / "plans" / f"{tid}.plan.md"
                    phases_file = cfg.workspace / ".ccc" / "phases" / f"{tid}.phases.json"
                    if plan_file.exists() and phases_file.exists():
                        # v0.24: 启动前跑一次 phase 依赖解析
                        phases = _load_phases(tid)
                        if phases:
                            executable, blocked, skipped = _resolve_phase_dependencies(phases)
                            if blocked or skipped:
                                _apply_phase_status_updates(tid, blocked, skipped)
                                engine_log(
                                    f"{tid} phase 依赖解析: executable={sorted(executable)} "
                                    f"blocked={sorted(blocked)} skipped={sorted(skipped)}"
                                )
                            # 如果所有 phase 都被跳过（依赖全失败）→ 把 task 也标 quarantined
                            if phases and all(
                                p.get("status") in ("skipped", "failed") or
                                (p.get("phase") in skipped)
                                for p in phases
                            ):
                                engine_log(
                                    f"{tid} 所有 phase 被跳过（依赖失败链），跳过 task 启动"
                                )
                                continue

                        running_task_id = tid
                        engine_log(f"取新 task: {tid}")
                        launch_r = dev_role_launch(tid)
                        if "error" in launch_r:
                            engine_log(f"启动 {tid} 失败: {launch_r['error']}")
                            running_task_id = None
                            continue  # 试下一个
                        update_index()  # v0.23.2 fix: 挪列后同步 index
                        break  # 启动了一个, 等下次轮询

                if running_task_id is None:
                    # 彻底无事可做
                    _check_stale()
                    _write_heartbeat(workspace, None)

                    # audit 触发检查（v0.22）：每 2h 跑一次全项目审计
                    if _audit_should_run(workspace):
                        engine_log("触发 audit_role（全项目扫描）")
                        try:
                            # 必须传 workspace 让 audit_role 把 last_run 写到 per-workspace 文件
                            ccc_board.audit_role(workspace=workspace)
                        except Exception as exc:
                            engine_log(f"audit_role 异常: {exc}")

                    # review 入站校验（v0.23.4）：检查 .ccc/reviews/ 新报告格式
                    _check_new_reviews()

                    time.sleep(cfg.engine_idle_sleep)
                    continue

        except KeyboardInterrupt:
            engine_log("收到 SIGINT, 优雅关闭")
            break
        except Exception as e:
            import traceback as _tb
            engine_log(f"异常: {e}")
            engine_log(f"  {_tb.format_exc().splitlines()[-2]}")  # 关键栈行
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
    except ImportError:
        pass  # 没有 _review_validator 时静默跳过
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
        except (ValueError, TypeError):
            pass

    # events TTL 清理：删 >30 天的事件文件
    try:
        store = _get_store(cfg.workspace)
        store.cleanup_events(max_days=30)
    except Exception:
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
        _log.error("[engine] 错误: %s 没有 .ccc/board/ 目录", ws)
        sys.exit(1)

    # 覆盖 workspace
    os.environ["CCC_WORKSPACE"] = str(ws)

    # 优雅关闭信号：设置全局标志，让主循环体面退出
    def _handle_sigterm(signum, frame):
        global _engine_shutdown
        if _engine_shutdown:
            return  # 二次 SIGTERM 不重复
        _engine_shutdown = True
        engine_log("收到 SIGTERM, 优雅关闭中...")

    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        engine_loop(str(ws))
    except KeyboardInterrupt:
        engine_log("Engine 关闭")
    except SystemExit:
        pass

    # 如果被 SIGTERM 触发关闭，等 10s 让 opencode 写完 .done
    if _engine_shutdown:
        remaining = 10
        while remaining > 0:
            time.sleep(1)
            remaining -= 1
        engine_log("Engine 终止")
    else:
        engine_log("Engine 正常退出")


if __name__ == "__main__":
    main()

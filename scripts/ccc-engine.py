#!/usr/bin/env python3
"""ccc-engine.py — CCC 多 workspace 并行执行引擎 (v0.28.1+)

替代「每 workspace 一个 engine 进程」模式。
单进程扫描 ~/program/* 下所有含 .ccc/board/ 的项目，全局 MAX_CONCURRENT=3 共享并发池。

使用方式:
  python3 ccc-engine.py

退出:
  Ctrl+C 或 SIGTERM → 优雅关闭
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# 确保当前目录在 path 中
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from _config import Config, get_logger
from _logger import add_file_handler
from _board_store import FileBoardStore
from _utils import now_iso as _utils_now_iso
from _stats_aggregator import aggregate_stats, load_summary

_log = get_logger("engine")

# ccc-board 在 import 时会 eager 绑定 ROOT；默认 workspace 供首次加载
os.environ.setdefault("CCC_WORKSPACE", str(_script_dir.parent))

# v0.28.2: Stats HTTP 默认端口（plan: engine-stats-endpoint）
_STATS_PORT = 7776

import importlib.util as _importlib_util

_ccc_board_path = str(_script_dir / "ccc-board.py")
_spec = _importlib_util.spec_from_file_location("ccc_board", _ccc_board_path)
ccc_board = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(ccc_board)

dev_role_launch = ccc_board.dev_role_launch
dev_role_relaunch = ccc_board.dev_role_relaunch
dev_role_check_complete = ccc_board.dev_role_check_complete
reviewer_role = ccc_board.reviewer_role
tester_role = ccc_board.tester_role
kb_role = ccc_board.kb_role
MAX_RETRY = ccc_board.MAX_RETRY

_load_phases = ccc_board._load_phases
_resolve_phase_dependencies = ccc_board._resolve_phase_dependencies
_apply_phase_status_updates = ccc_board._apply_phase_status_updates
_check_phase_failures = ccc_board._check_phase_failures
_current_running_phase = ccc_board._current_running_phase

cfg = Config()

# 日志轮转：engine.log + daily rotate + keep 7 days
_log_dir = Path(os.environ.get("HOME", str(Path.home()))) / ".ccc" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = str(_log_dir / "engine.log")
add_file_handler("engine", _log_file, when="midnight", interval=1, backup_count=7)

_log.info(
    "ccc-engine config: phase_timeout=%ds, exec_timeout=%ds, engine_tick_interval=%ds",
    cfg.phase_timeout,
    cfg.exec_timeout,
    cfg.engine_tick_interval,
)

_engine_shutdown = False
_MAX_PRODUCT_RETRIES = 3
MAX_CONCURRENT = 3

# v0.28.2: Phase 并行调度（plan: engine-phase-parallel-dispatch）
PHASE_PARALLEL_MAX_WORKERS = 2


def _set_parallel_disabled(val: bool) -> None:
    """Set the global PHASE_PARALLEL_DISABLED toggle (module-level)."""
    global PHASE_PARALLEL_DISABLED
    PHASE_PARALLEL_DISABLED = val


PHASE_PARALLEL_DISABLED = False  # 故障 fallback 时设为 True（仅当次 Engine tick）

_stores: dict[str, FileBoardStore] = {}

# Per-task 并行 phase 状态：
#   task_key -> {
#     "groups": [[phase_num, ...], ...],   # 待执行的 group 列表（每组内并行）
#     "current_group": [phase_num, ...] | None,  # 当前正在跑的 group
#     "phase_meta": {phase_num: {subid, pid, started_at}}
#   }
_parallel_phases: dict[str, dict] = {}

# backlog+planned 为空时的补充冷却（per-workspace，单位秒）
_last_empty_replenish: dict[str, float] = {}

# v0.31+: hang 自动重启（plan: executor-auto-restart）
_MAX_HANG_RETRY = 2  # 单个 task 最多自动重启 hung 的次数
_hang_retry_counter: dict[str, int] = {}  # task_key -> retry count

# v0.31+: hang 检测（plan: executor-hang-detection）
# Phase 4 of the pipeline: detect → write .hung → Phase 5 consumes it.
_HANG_CHECK_INTERVAL_SEC = 300  # 5 分钟无活动判定为 hung


def now_iso() -> str:
    return _utils_now_iso()


def engine_log(msg: str, *args: str) -> None:
    if args:
        msg = msg % args
    _log.info("%s", msg)


# ── Stats 日志（结构化 JSONL，供 AI 分析用）──
_STATS_DIR: Path | None = None


def _stats_dir(ws: Path) -> Path:
    global _STATS_DIR
    if _STATS_DIR is None:
        _STATS_DIR = ws / ".ccc" / "stats"
        _STATS_DIR.mkdir(parents=True, exist_ok=True)
    return _STATS_DIR


def _log_stats(ws: Path, event: str, tid: str, **extra) -> None:
    """写一条结构化事件到 .ccc/stats/events.jsonl。"""
    sf = _stats_dir(ws) / "events.jsonl"
    record = {
        "t": now_iso(),
        "event": event,
        "task": tid,
        "workspace": ws.name,
    }
    record.update(extra)
    try:
        with sf.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


_NOTIFY_SCRIPT = _script_dir / "ccc-notify.sh"


def _ccc_notify(title: str, message: str) -> None:
    """非阻塞 macOS 桌面通知（Engine 主循环不等待）。"""
    if not _NOTIFY_SCRIPT.is_file():
        engine_log(f"notify 跳过: {_NOTIFY_SCRIPT} 不存在")
        return
    try:
        subprocess.Popen(
            ["bash", str(_NOTIFY_SCRIPT), title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        engine_log(f"notify 失败: {exc}")


def _quarantine_with_notify(
    ws: Path,
    tid: str,
    reason: str,
    store: FileBoardStore | None = None,
    phase: int = 1,
) -> None:
    """移入 abnormal 并触发桌面通知。"""
    _activate_workspace(ws)
    if store is None:
        store = _get_store(ws)
    store.quarantine(tid, reason)
    _log_stats(ws, "quarantine", tid, reason=reason)
    _ccc_notify("CCC", f"任务 {tid} 进入异常状态，原因：{reason}")
    store.update_index()
    # v0.31: 记录教训
    try:
        from _lessons import record_failure

        record_failure(ws, tid, phase, reason or "unknown", "")
    except Exception:
        pass


def _discover_workspaces() -> list[Path]:
    """扫描 ~/program/* 及 ~/program/projects/* 下含 .ccc/board/ 的目录。"""
    program_dir = Path.home() / "program"
    if not program_dir.is_dir():
        return []

    candidates: list[Path] = []
    for p in sorted(program_dir.iterdir()):
        if p.is_dir():
            candidates.append(p)
    projects_dir = program_dir / "projects"
    if projects_dir.is_dir():
        for p in sorted(projects_dir.iterdir()):
            if p.is_dir():
                candidates.append(p)

    workspaces: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p.resolve())
        if key in seen:
            continue
        if (p / ".ccc" / "board").is_dir():
            workspaces.append(p.resolve())
            seen.add(key)
    return workspaces


def _ws_label(ws: Path, program_dir: Path | None = None) -> str:
    program_dir = program_dir or (Path.home() / "program")
    try:
        return ws.relative_to(program_dir).as_posix()
    except ValueError:
        return ws.name


def _task_key(ws: Path, tid: str) -> str:
    return f"{ws.resolve()}|{tid}"


def _activate_workspace(ws: Path) -> Path:
    """切换当前 workspace：env + ccc-board lazy 缓存 + ROOT 补丁。"""
    ws = ws.resolve()
    os.environ["CCC_WORKSPACE"] = str(ws)
    ccc_board._reset_lazy()
    ccc_board.ROOT = ws
    ccc_board.BOARD = ws / ".ccc" / "board"
    ccc_board.EVENTS_DIR = ccc_board.BOARD / "events"
    return ws


def _get_store(workspace: Path) -> FileBoardStore:
    key = str(workspace.resolve())
    if key not in _stores:
        _stores[key] = FileBoardStore(workspace)
    return _stores[key]


_BOARD_COLUMNS = (
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
)


def _verdict_file(ws: Path, tid: str) -> Path:
    return ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"


def _verdict_is_valid(ws: Path, tid: str) -> bool:
    """verdict 文件必须存在且非空（空文件视为未产出）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        return bool(vf.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def _find_task_column(store: FileBoardStore, tid: str) -> str | None:
    for col in _BOARD_COLUMNS:
        if any(t["id"] == tid for t in store.list_tasks(col)):
            return col
    return None


def _ensure_task_in_testing(store: FileBoardStore, tid: str) -> None:
    """reviewer 可能提前挪 verified；拉回 testing 以便 tester/pytest 门禁。"""
    if _find_task_column(store, tid) == "verified":
        store.move_task(tid, "verified", "testing")


def _run_pytest(ws: Path) -> tuple[int, str]:
    """在 workspace 跑 pytest tests/；有 .venv 则走 .venv/bin/pytest。"""
    venv_pytest = ws / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "tests/", "-q", "--tb=line"]
    else:
        cmd = ["python3", "-m", "pytest", "tests/", "-q", "--tb=line"]
    try:
        r = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=cfg.phase_timeout,
        )
        output = (r.stdout or "") + (r.stderr or "")
        return r.returncode, output
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return 124, output or "pytest timeout (600s)"
    except OSError as exc:
        return 1, str(exc)


def _record_pytest_failure(ws: Path, tid: str, exit_code: int, output: str) -> None:
    """pytest 失败时追加记录到 verdict 文件，供人工确认。"""
    vf = _verdict_file(ws, tid)
    vf.parent.mkdir(parents=True, exist_ok=True)
    snippet = output[-2000:] if output else "(无输出)"
    section = (
        f"\n\n## Engine pytest 检查\n\n"
        f"- **退出码**: {exit_code}\n\n"
        f"```\n{snippet}\n```\n"
    )
    try:
        if vf.is_file():
            vf.write_text(vf.read_text(encoding="utf-8") + section, encoding="utf-8")
        else:
            vf.write_text(
                f"# Verdict: {tid}\n\n**FAIL** (engine pytest)\n{section}",
                encoding="utf-8",
            )
    except OSError as exc:
        engine_log(f"写入 pytest 失败记录到 verdict 失败: {exc}")


def _verdict_is_timeout(ws: Path, tid: str) -> bool:
    """检查 verdict 文件是否标记为 TIMEOUT（reviewer LLM 超时但未 quarantine）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        content = vf.read_text(encoding="utf-8")
        return "**Verdict:** TIMEOUT" in content
    except OSError:
        return False


def _clear_verdict(ws: Path, tid: str) -> None:
    """删除 verdict 文件，使 _verdict_is_valid 返回 False，触发 engine 重试。"""
    vf = _verdict_file(ws, tid)
    try:
        vf.unlink(missing_ok=True)
    except OSError:
        pass


def _run_reviewer_tester_gate(ws: Path, tid: str) -> bool:
    """reviewer verdict + tester + engine pytest 双门禁。通过才移 verified。

    v0.31+: 超时情形 engine 层自动重试（不 quarantine），
    reviewer_retry_on_timeout 次超时后再 quarantine。
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    timeout_retries = cfg.reviewer_retry_on_timeout
    timeout_count = 0
    verdict_ok = False
    max_attempts = max(2, timeout_retries)

    for attempt in range(max_attempts):
        reviewer_role()
        if _verdict_is_valid(ws, tid):
            if _verdict_is_timeout(ws, tid):
                timeout_count += 1
                if timeout_count >= timeout_retries:
                    engine_log(
                        f"[{label}] {tid} reviewer 超时重试 {timeout_count}/{timeout_retries} 耗尽 → abnormal"
                    )
                    cur_phase = _current_running_phase(tid)
                    _quarantine_with_notify(
                        ws, tid, "reviewer 超时重试耗尽", store, phase=cur_phase
                    )
                    return False
                _clear_verdict(ws, tid)
                _ensure_task_in_testing(store, tid)
                engine_log(
                    f"[{label}] {tid} reviewer 超时，等待重试 (attempt {attempt + 1}/{timeout_retries})"
                )
                time.sleep(30)
                continue
            verdict_ok = True
            break

        engine_log(
            f"[{label}] {tid} reviewer 未产出有效 verdict (attempt {attempt + 1}/{max_attempts})"
        )
        _ensure_task_in_testing(store, tid)
        if attempt == max_attempts - 1 and not verdict_ok:
            engine_log(f"[{label}] {tid} reviewer verdict 重试耗尽 → abnormal")
            cur_phase = _current_running_phase(tid)
            _quarantine_with_notify(
                ws, tid, "reviewer 未产出 verdict", store, phase=cur_phase
            )
            store.update_index()
            return False

    _ensure_task_in_testing(store, tid)

    try:
        tester_role()
    except Exception as exc:
        engine_log(f"[{label}] {tid} tester_role 异常: {exc}")

    _ensure_task_in_testing(store, tid)

    tests_dir = ws / "tests"
    if tests_dir.is_dir():
        exit_code, output = _run_pytest(ws)
        _log_stats(ws, "pytest", tid, exit_code=exit_code, output_len=len(output))
        if exit_code != 0:
            _record_pytest_failure(ws, tid, exit_code, output)
            engine_log(
                f"[{label}] {tid} pytest 失败 (exit={exit_code})，留在 testing 等待人工确认"
            )
            _ccc_notify(
                "CCC", f"任务 {tid} pytest 未通过 (exit={exit_code})，已留在 testing"
            )
            store.update_index()
            return False
    else:
        engine_log(f"[{label}] {tid} 无 tests/ 目录，跳过 engine pytest")

    if verdict_ok:
        col = _find_task_column(store, tid)
        if col == "testing":
            store.move_task(tid, "testing", "verified")
            _log_stats(ws, "move", tid, from_col="testing", to_col="verified")
        store.update_index()
        return _find_task_column(store, tid) == "verified"

    store.update_index()
    return False


def _run_testing_tasks_gate(ws: Path) -> None:
    """对 testing 列每个 task 跑 reviewer/tester 门禁。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    for task in store.list_tasks("testing"):
        tid = task["id"]
        engine_log(f"[{label}] testing 门禁: {tid}")
        try:
            _run_reviewer_tester_gate(ws, tid)
        except Exception as exc:
            engine_log(f"[{label}] {tid} reviewer/tester 门禁异常: {exc}")


def _handle_task_result(ws: Path, tid: str, result: dict, complexity: str) -> bool:
    """处理 dev_role_check_complete 结果。返回 True 表示从 active_tasks 移除。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    status = result.get("status", "unknown")

    if status == "success":
        if complexity == "small":
            engine_log(
                f"[{label}] {tid} complexity=small, 跳过 reviewer+tester → 直通 kb"
            )
            store.move_task(tid, "in_progress", "testing")
            _log_stats(ws, "move", tid, from_col="in_progress", to_col="testing")
            store.move_task(tid, "testing", "verified")
            _log_stats(ws, "move", tid, from_col="testing", to_col="verified")
            verified = store.list_tasks("verified")
            if any(t["id"] == tid for t in verified):
                engine_log(f"[{label}] {tid} → verified, 立即 kb")
                kb_role()
                try:
                    auto_r = ccc_board.auto_approve_agents()
                    if auto_r.get("approved", 0) > 0:
                        engine_log(f"auto-approve-agents ✓ {auto_r['approved']} 条建议")
                except Exception as exc:
                    engine_log(f"auto_approve_agents 异常: {exc}")
                engine_log(f"[{label}] {tid} 全链路完成 (small path)")
            else:
                engine_log(f"[{label}] {tid} small path: 移入 verified 失败")
            store.update_index()
            return True

        _log_stats(ws, "move", tid, from_col="in_progress", to_col="testing")
        engine_log(f"[{label}] {tid} → testing, 立即跑 reviewer+tester 门禁")
        gate_ok = _run_reviewer_tester_gate(ws, tid)

        verified = store.list_tasks("verified")
        if gate_ok and any(t["id"] == tid for t in verified):
            engine_log(f"[{label}] {tid} → verified, 立即 kb")
            kb_role()
            try:
                auto_r = ccc_board.auto_approve_agents()
                if auto_r.get("approved", 0) > 0:
                    engine_log(
                        f"auto-approve-agents ✓ {auto_r['approved']} 条建议合入 AGENTS.md"
                    )
            except Exception as exc:
                engine_log(f"auto_approve_agents 异常: {exc}")
            engine_log(f"[{label}] {tid} 全链路完成")
        else:
            engine_log(f"[{label}] {tid} reviewer/tester 未通过")

        store.update_index()
        return True

    if status == "failed":
        retry = result.get("retry", 0)
        failure_summary = _check_phase_failures(tid)
        if failure_summary.get("all_failed_or_skipped"):
            engine_log(
                f"[{label}] {tid} 所有 phase failed/skipped "
                f"(skipped={failure_summary.get('skipped')})"
            )
            store.update_index()
            return True
        cur = _current_running_phase(tid)
        engine_log(f"[{label}] {tid} 失败 (retry={retry}), relaunch phase {cur}")
        dev_role_relaunch(tid)
        return False

    if status == "quarantined":
        failure_summary = _check_phase_failures(tid)
        if failure_summary.get("all_failed_or_skipped"):
            engine_log(
                f"[{label}] {tid} 所有 phase failed/skipped → abnormal "
                f"(skipped_downstream={failure_summary['skipped']})"
            )
        else:
            engine_log(f"[{label}] {tid} 重试耗尽, 已隔离, 移向下一个")
        store.update_index()
        return True

    if status == "not_found":
        engine_log(f"[{label}] {tid} 不在 in_progress (可能已被外部移走)")
    else:
        engine_log(f"[{label}] {tid} 未知状态: {status}")
    return True


def _recover_tasks(ws: Path, active_tasks: dict[str, dict]) -> None:
    """Engine 启动后扫描 board，恢复 in_progress/testing 列的 task 上下文。

    验收点：
      - in_progress 列 task: 调 dev_role_check_complete 恢复 phase 执行状态
      - testing 列 task: 调 reviewer_role + tester_role 恢复验收流程
      - 每恢复一个 task 间隔 5s，避免并发重启风暴
      - board 为空时静默跳过，无日志噪声

    Args:
        ws: workspace 路径
        active_tasks: 引擎活跃 task 表（恢复后的 task 会填充到此 dict）
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    in_prog = store.list_tasks("in_progress")
    testing = store.list_tasks("testing")

    if not in_prog and not testing:
        engine_log(f"[{label}] board 为空，跳过 task 恢复")
        return

    if in_prog:
        engine_log(
            f"[recover] [{label}] 恢复 {len(in_prog)} 个 in_progress task "
            f"（间隔 5s 避免并发）"
        )

    for idx, task in enumerate(in_prog):
        tid = task["id"]
        complexity = task.get("complexity", "medium")
        cur_phase = _current_running_phase(tid)
        engine_log(
            f"[recover] [{label}] Recovered task {tid} at phase {cur_phase} "
            f"（in_progress → dev 检查）"
        )
        try:
            result = dev_role_check_complete(tid)
            status = result.get("status", "unknown")
            key = _task_key(ws, tid)
            if status == "running":
                active_tasks[key] = {
                    "workspace": ws,
                    "task_id": tid,
                    "complexity": complexity,
                    "started_at": now_iso(),
                }
                engine_log(f"[recover] [{label}] {tid} PID 仍存活，继续监控")
            else:
                _handle_task_result(ws, tid, result, complexity)
        except Exception as exc:
            engine_log(f"[recover] [{label}] {tid} in_progress 恢复异常: {exc}")

        if idx < len(in_prog) - 1:
            time.sleep(5)

    if testing:
        engine_log(
            f"[recover] [{label}] 恢复 {len(testing)} 个 testing task "
            f"（间隔 5s 避免并发）"
        )

    for idx, task in enumerate(testing):
        tid = task["id"]
        engine_log(f"[recover] [{label}] Recovered task {tid} at phase reviewing")
        try:
            try:
                reviewer_role()
            except Exception as exc:
                engine_log(f"[recover] [{label}] {tid} reviewer 异常: {exc}")
            try:
                tester_role()
            except Exception as exc:
                engine_log(f"[recover] [{label}] {tid} tester 异常: {exc}")
        except Exception as exc:
            engine_log(f"[recover] [{label}] {tid} testing 恢复异常: {exc}")

        if idx < len(testing) - 1:
            time.sleep(5)


def _startup_scan_workspace(ws: Path, active_tasks: dict[str, dict]) -> None:
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    in_prog = store.list_tasks("in_progress")
    if in_prog:
        engine_log(f"[{label}] 发现 {len(in_prog)} 个 in_progress 任务，恢复检查")
    for task in in_prog:
        tid = task["id"]
        key = _task_key(ws, tid)
        complexity = task.get("complexity", "medium")
        result = dev_role_check_complete(tid)
        status = result.get("status", "unknown")
        if status == "running":
            active_tasks[key] = {
                "workspace": ws,
                "task_id": tid,
                "complexity": complexity,
                "started_at": now_iso(),
            }
            engine_log(f"[{label}] {tid} 检查 PID 存活")
        elif status in ("success", "failed"):
            engine_log(f"[{label}] {tid} 已完成 (status={status}), 继续链")
            if not _handle_task_result(ws, tid, result, complexity):
                active_tasks[key] = {
                    "workspace": ws,
                    "task_id": tid,
                    "complexity": complexity,
                    "started_at": now_iso(),
                }
        else:
            _handle_task_result(ws, tid, result, complexity)


def _process_backlog(ws: Path) -> bool:
    """消费 backlog 首条 task。返回 True 表示做了操作。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    backlog = store.list_tasks("backlog")
    if not backlog:
        return False

    tid = backlog[0]["id"]
    phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if phases_file.exists():
        engine_log(
            f"[product] [{label}] {tid} phases.json 已存在，跳过 product_role（手动拆分），移入 planned"
        )
        store.move_task(tid, "backlog", "planned")
        _log_stats(ws, "move", tid, from_col="backlog", to_col="planned")
        return True

    fail_counter_dir = ws / ".ccc" / ".product-fail-counter"
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
            f"[product] [{label}] {tid} 已失败 {fail_count} 次 >= {_MAX_PRODUCT_RETRIES}，移入 abnormal"
        )
        _quarantine_with_notify(
            ws, tid, f"product_role 连续失败 {fail_count} 次", store, phase=0
        )
        _ccc_notify(
            "CCC",
            f"product_role 拆分 {tid} 连续失败 {fail_count} 次",
        )
        return True

    engine_log(
        f"[product] [{label}] backlog 自动拆分: {tid} (此前失败 {fail_count} 次)"
    )
    try:
        _log_stats(ws, "product_start", tid, fail_count=fail_count)
        ccc_board.product_role(task_id=tid)
        if fail_counter_path.exists():
            fail_counter_path.unlink()
        _log_stats(ws, "product_done", tid, fail_count=fail_count)
    except Exception as exc:
        fail_count += 1
        fail_counter_dir.mkdir(parents=True, exist_ok=True)
        fail_counter_path.write_text(json.dumps({"fail_count": fail_count}, indent=2))
        _log_stats(ws, "product_fail", tid, fail_count=fail_count, error=str(exc)[:200])
        engine_log(
            f"[product] [{label}] product_role({tid}) 异常: {exc} (失败 #{fail_count})"
        )
        if fail_count >= _MAX_PRODUCT_RETRIES:
            engine_log(
                f"[product] [{label}] {tid} 失败 {fail_count} 次 >= {_MAX_PRODUCT_RETRIES}，移入 abnormal"
            )
            _quarantine_with_notify(
                ws, tid, f"product_role 连续失败 {fail_count} 次", store, phase=0
            )
            _ccc_notify(
                "CCC",
                f"product_role 拆分 {tid} 连续失败 {fail_count} 次",
            )
    return True


def _auto_replenish_backlog(ws: Path, store, program_dir: Path) -> bool:
    """backlog + planned 都为空时，立即触发 audit_role 补充新任务。

    绕过 _audit_should_run 的 2h 间隔，但有 5min per-workspace 冷却
    避免 audit_role 在无变更的项目上空转。

    Returns: True 表示触发了 audit_role
    """
    if store.list_tasks("backlog"):
        return False
    if store.list_tasks("planned"):
        return False

    now = time.time()
    ws_key = str(ws)
    last = _last_empty_replenish.get(ws_key, 0.0)
    if now - last <= 300:
        return False

    _last_empty_replenish[ws_key] = now
    label = _ws_label(ws, program_dir)
    engine_log(f"[{label}] backlog+planned 均为空，立即触发 audit_role 补充")
    try:
        ccc_board.audit_role(workspace=str(ws))
    except Exception as exc:
        engine_log(f"[{label}] audit_role 异常: {exc}")
    return True


# ═══════════════════════════════════════════════════════════════
# v0.28.2: Phase 并行调度（plan: engine-phase-parallel-dispatch）
# ═══════════════════════════════════════════════════════════════


def _phase_market_subid(tid: str, phase_num: int) -> str:
    """Per-phase marker subid，避免并行 phase 写在同 task_id.{done,pid,exitcode}。

    用「task_id__p{N}」双下划线，与 ccc-board 的「task_id-p{N}」区分。
    """
    return f"{tid}__p{phase_num}"


def _group_parallel_phases(phases: list[dict], executable: set[int]) -> list[list[int]]:
    """将 executable phases 分组：同组内 phase 之间无 depends_on 关系。

    Args:
        phases: 所有 phase dict（来自 _load_phases）
        executable: 当前可执行的 phase id 集合（来自 _resolve_phase_dependencies）

    Returns:
        list[list[int]]：每个内层 list 是一组可并行 phase（组内相位无依赖）。
        多组间必须先后顺序执行（前组全部完成才执行下一组）。

    算法：贪心。每个 phase 顺序遍历 — 能加入最后一个 group 当存在互不依赖，
    否则开新 group。
    """
    if not executable:
        return []
    by_id = {p.get("phase"): p for p in phases if p.get("phase") is not None}
    sorted_executable = sorted(executable)
    groups: list[list[int]] = []
    for pid in sorted_executable:
        phase_deps = set(by_id.get(pid, {}).get("depends_on") or [])
        placed = False
        # 尝试放入最后一个 group
        if groups:
            last_group = groups[-1]
            last_group_ids = set(last_group)
            # 若本 phase 与组内所有 phase 不互依赖（last_group_ids ∩ phase_deps == ∅）
            # 且组内其他 phase 也不依赖本 phase（避免环）
            conflicts = last_group_ids & phase_deps
            reverse_deps_conflict = any(
                pid in set(by_id.get(g, {}).get("depends_on") or []) for g in last_group
            )
            if not conflicts and not reverse_deps_conflict:
                last_group.append(pid)
                placed = True
        if not placed:
            groups.append([pid])
    return groups


def _phase_to_pgroup(p: int) -> str:
    """OpenCode pool / marker 用的 phase id（与 ccc-board 一致：task_id-pN）。"""
    # 注：当前 _try_launch_planned 调 dev_role_launch，里头 phase_id=task_id-pN。
    # 本 dispatcher 用 pgroup = task_id__pN 双下划线以隔离 task-level 标记。
    return f"p{p}"


def _build_phase_prompt(task_id: str, phase_num: int, plan_content: str) -> str:
    """构造单 phase 的 prompt（与 ccc-board.dev_role_launch 相同模板，确保 dev 行为一致）。"""
    return (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## Plan\n\n{plan_content}\n\n"
        f"## 完成定义\n"
        f"1. 实现所有需求\n"
        f"2. 跑对应的测试（如有）\n"
        f"3. 提交一个 commit（message 以 {task_id} 开头）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 plan 文件白名单\n"
    )


def _launch_parallel_phase(
    ws: Path,
    task_id: str,
    phase_num: int,
    plan_content: str,
    timeout_s: int,
    label: str,
) -> dict | None:
    """启单个 phase 的 opencode-runner.sh 后台进程，用 per-phase 命名空间隔离。

    Returns:
        {"subid": str, "pid": int, "proc": Popen} 或 None（失败）。
    """
    import subprocess as _sp

    subid = _phase_market_subid(task_id, phase_num)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir = Path.home() / ".ccc" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{subid}.prompt.md"
    prompt_file.write_text(
        _build_phase_prompt(task_id, phase_num, plan_content),
        encoding="utf-8",
    )
    try:
        # 用 phase_id = subid 命名 opencode-runner.sh 的输出 marker
        # opencode-runner.sh 内部会写 ${PID_DIR}/${TASK_ID}.{done,exitcode}
        # 这里 TASK_ID 用 subid，故 marker 也隔离。
        proc = _sp.Popen(
            [
                "bash",
                str(_script_dir / "opencode-runner.sh"),
                subid,
                str(_script_dir.parent),  # CCC_HOME
                str(ws),  # ROOT_DIR
                "--phase",
                f"{task_id}-p{phase_num}",  # 与 ccc-board 一致 phase_id 命名
                "--prompt",
                str(prompt_file),
                "--timeout",
                str(timeout_s),
                "--cwd",
                str(ws),
            ],
            cwd=ws,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pids_dir.joinpath(f"{subid}.pid").write_text(str(proc.pid))
        engine_log(
            f"[{label}] {task_id}-p{phase_num} launched PID={proc.pid} "
            f"(subid={subid}, retry 0/{cfg.DEFAULT_RETRY}, timeout {timeout_s}s)"
        )
        return {"subid": subid, "pid": proc.pid, "proc": proc}
    except Exception as exc:
        engine_log(f"[{label}] {task_id}-p{phase_num} launch failed: {exc}")
        return None


def _check_parallel_phase_done(ws: Path, subid: str) -> dict:
    """检查单个并行 phase 完成状态。

    Returns:
        {"status": "running" | "success" | "failed", "exit_code": int}
    """
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{subid}.done"
    if not done_file.exists():
        # 检查 PID 是否存活
        pid_file = pids_dir / f"{subid}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"status": "running", "exit_code": -1}
            except (ValueError, OSError, ProcessLookupError):
                pass
        return {"status": "running", "exit_code": -1}
    exit_file = pids_dir / f"{subid}.exitcode"
    try:
        exit_code = int(exit_file.read_text().strip()) if exit_file.exists() else 1
    except ValueError:
        exit_code = 1
    return {
        "status": "success" if exit_code == 0 else "failed",
        "exit_code": exit_code,
    }


def _launch_parallel_group(
    ws: Path,
    task_id: str,
    phase_nums: list[int],
    plan_content: str,
    timeout_s: int,
    label: str,
) -> tuple[bool, dict[int, dict]]:
    """并行启一组 phase（max_workers 个线程）。返回 (success, phase_meta)。

    Args:
        phase_nums: 这组 phase 编号列表
        plan_content: 完整 plan 文本（每个 phase 都用同一份 prompt）
        timeout_s: 超时秒数

    Returns:
        (True, {phase_num: {"subid": ..., "pid": ...}}) 全部成功
        (False, {...}) 部分/全部失败
    """
    if not phase_nums:
        return True, {}

    max_w = min(PHASE_PARALLEL_MAX_WORKERS, len(phase_nums))
    engine_log(
        f"[parallel] [{label}] {task_id} 并行启动 "
        f"phase {' + '.join(f'phase-{n}' for n in phase_nums)} "
        f"(max_workers={max_w})"
    )
    phase_meta: dict[int, dict] = {}
    try:
        with ThreadPoolExecutor(max_workers=max_w) as ex:
            futures = {
                ex.submit(
                    _launch_parallel_phase,
                    ws,
                    task_id,
                    pn,
                    plan_content,
                    timeout_s,
                    label,
                ): pn
                for pn in phase_nums
            }
            for fut, pn in futures.items():
                try:
                    res = fut.result(timeout=15)
                except Exception as exc:
                    engine_log(
                        f"[{label}] {task_id}-p{pn} parallel submit exception: {exc}"
                    )
                    res = None
                if res is None:
                    engine_log(
                        f"[parallel][warn] {task_id}-p{pn} 启动失败，"
                        f"此 phase 将被跳过（其他 phase 继续）"
                    )
                    continue
                phase_meta[pn] = res
        success = len(phase_meta) > 0
        if success:
            engine_log(
                f"[parallel] [{label}] {task_id} 并行 phase 已启动: "
                f"{[(pn, phase_meta[pn]['pid']) for pn in sorted(phase_meta)]}"
            )
        return success, phase_meta
    except Exception as exc:
        engine_log(
            f"[parallel][warn] {task_id} ThreadPoolExecutor 异常: {exc}，"
            f"fallback 串行模式"
        )
        _set_parallel_disabled(True)
        return False, {}


def _try_launch_planned(ws: Path, active_tasks: dict[str, dict]) -> bool:
    """从 planned 启动一个 task。返回 True 表示已启动。

    v0.28.2: 当 executable phase 数 >= 2 且未禁用并行时，走并行分支；
    失败时 fallback 到单 phase 串行 dev_role_launch。
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    planned = store.list_tasks("planned")
    for task in planned:
        tid = task["id"]
        key = _task_key(ws, tid)
        if key in active_tasks:
            continue
        plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
        phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
        if not plan_file.exists() or not phases_file.exists():
            continue

        phases = _load_phases(tid)
        executable: set[int] = set()
        if phases:
            executable, blocked, skipped = _resolve_phase_dependencies(phases)
            if blocked or skipped:
                _apply_phase_status_updates(tid, blocked, skipped)
                engine_log(
                    f"[{label}] {tid} phase 依赖解析: executable={sorted(executable)} "
                    f"blocked={sorted(blocked)} skipped={sorted(skipped)}"
                )
            if phases and all(
                p.get("status") in ("skipped", "failed") or (p.get("phase") in skipped)
                for p in phases
            ):
                engine_log(
                    f"[{label}] {tid} 所有 phase 被跳过（依赖失败链），跳过 task 启动"
                )
                continue

        complexity = task.get("complexity", "medium")
        engine_log(f"[{label}] 取新 task: {tid} (complexity={complexity})")

        # ── v0.28.2: 并行分支 ──
        # 条件：executable phase >= 2 + 未被全局禁用
        # 不满足则直接走单 phase dev_role_launch（原有路径）
        if (
            phases
            and executable
            and len(executable) >= 2
            and not PHASE_PARALLEL_DISABLED
        ):
            groups = _group_parallel_phases(phases, executable)
            if groups and len(groups[0]) >= 2:
                plan_content = plan_file.read_text(encoding="utf-8")
                timeout_s = _lookup_phase_timeout(tid, phases)
                ok = _try_launch_planned_parallel(
                    ws, tid, groups, plan_content, timeout_s
                )
                if ok:
                    store.move_task(tid, "planned", "in_progress")
                    active_tasks[key] = {
                        "workspace": ws,
                        "task_id": tid,
                        "complexity": complexity,
                        "started_at": now_iso(),
                        "mode": "parallel",
                    }
                    store.update_index()
                    return True
                # 并行启动失败 → 回退串行
                engine_log(f"[{label}] {tid} 并行启动失败，回退 dev_role_launch 串行")

        launch_r = dev_role_launch(tid)
        if "error" in launch_r:
            engine_log(f"[{label}] 启动 {tid} 失败: {launch_r['error']}")
            continue
        active_tasks[key] = {
            "workspace": ws,
            "task_id": tid,
            "complexity": complexity,
            "started_at": now_iso(),
        }
        store.update_index()
        return True
    return False


def _lookup_phase_timeout(tid: str, phases: list[dict]) -> int:
    """查 phases 里 phase 1 的 timeout，单位秒；找不到走 cfg.default_timeout。

    engine-phase-retry-config: 缺省 600 → cfg.default_timeout（1800），
    与 ccc-board._load_timeout 默认值保持一致。
    """
    default_to = cfg.default_timeout
    for p in phases:
        if p.get("phase") == 1:
            try:
                return int(p.get("timeout", default_to))
            except (TypeError, ValueError):
                return default_to
    return default_to


def _store_atomic_write_phases(path: Path, payload: str) -> None:
    """原子写 phases.json：写 temp + os.replace。容错 fallback 直写。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            path.write_text(payload, encoding="utf-8")
        except OSError:
            pass


def _try_launch_planned_parallel(
    ws: Path,
    task_id: str,
    groups: list[list[int]],
    plan_content: str,
    timeout_s: int,
) -> bool:
    """启并行 task 的首个 group，剩余 group 等当前 group 全部完成后再启。

    Args:
        ws: workspace 路径
        task_id: task 名
        groups: 分组后的并行 phase 列表（每组内无相互依赖）
        plan_content: 完整 plan 文本
        timeout_s: 单 phase 超时秒数

    Returns:
        True 至少启了一个 phase；False 全部失败。
    """
    global _parallel_phases

    label = _ws_label(ws)
    key = _task_key(ws, task_id)
    first_group = groups[0]
    engine_log(
        f"[parallel] [{label}] {task_id} 并行调度: {len(groups)} 个 group "
        f"(size={[len(g) for g in groups]}, max_workers={min(PHASE_PARALLEL_MAX_WORKERS, len(first_group))})"
    )
    success, phase_meta = _launch_parallel_group(
        ws, task_id, first_group, plan_content, timeout_s, label
    )
    if not success:
        engine_log(f"[parallel][error] [{label}] {task_id} 全部 phase 启动失败")
        return False
    _parallel_phases[key] = {
        "groups": groups,
        "current_group": first_group,
        "phase_meta": phase_meta,
        "any_group_fail": False,
        "ws_path": str(ws),
    }
    engine_log(
        f"[parallel] [{label}] {task_id} 当前 group={first_group} 启动 {len(phase_meta)} phase OK"
    )
    return True


def _on_parallel_group_complete(ws: Path, task_id: str, phase_nums: list[int]) -> str:
    """检一组并行 phase 是否都写完 marker。

    Returns:
        "still_running" — 仍有 phase 没标 done
        "group_done_ok" — 全部 phase 成功
        "group_done_fail" — 至少 1 条失败
    """
    ws = ws.resolve()
    pids_dir = ws / ".ccc" / "pids"
    exitcodes: dict[int, int] = {}
    for pid in phase_nums:
        subid = _phase_market_subid(task_id, pid)
        done_path = pids_dir / f"{subid}.done"
        exit_path = pids_dir / f"{subid}.exitcode"
        if not done_path.exists():
            return "still_running"
        try:
            ec = int(exit_path.read_text().strip()) if exit_path.exists() else 1
        except (ValueError, OSError):
            ec = 1
        exitcodes[pid] = ec
    label = _ws_label(ws)
    any_fail = any(ec != 0 for ec in exitcodes.values())
    engine_log(
        f"[parallel][group-done] [{label}] {task_id} group {phase_nums} → "
        f"{'fail' if any_fail else 'ok'} (exitcodes={exitcodes})"
    )
    # 写回 phases.json：pending → done/failed
    phases_file = ws / ".ccc" / "phases" / f"{task_id}.phases.json"
    if phases_file.exists():
        try:
            raw = phases_file.read_text(encoding="utf-8")
            new_lines: list[str] = []
            changed = False
            for line in raw.splitlines():
                s = line.strip()
                if not s:
                    new_lines.append(line)
                    continue
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue
                if not isinstance(obj, dict) or "phase" not in obj:
                    new_lines.append(line)
                    continue
                pid = obj.get("phase")
                if pid in exitcodes:
                    new_status = "done" if exitcodes[pid] == 0 else "failed"
                    if obj.get("status") != new_status:
                        obj["status"] = new_status
                        changed = True
                new_lines.append(json.dumps(obj, ensure_ascii=False))
            if changed:
                _store_atomic_write_phases(phases_file, "\n".join(new_lines) + "\n")
        except OSError as exc:
            engine_log(f"[parallel][status] 写 phases.json 失败: {exc}")
    return "group_done_fail" if any_fail else "group_done_ok"


def _check_parallel_task_complete(ws: Path, task_id: str) -> str:
    """Engine tick 调用：推进并行 task 状态。

    Returns:
        "still_running" — 当前 group 未完 / 等待下一 group
        "task_complete_ok" — 全部 group 完成且全成功
        "task_complete_fail" — 有 group 失败
    """
    global _parallel_phases

    ws = ws.resolve()
    key = _task_key(ws, task_id)
    state = _parallel_phases.get(key)
    if not state:
        return "still_running"

    current_group = state.get("current_group") or []
    if not current_group:
        return "still_running"

    group_state = _on_parallel_group_complete(ws, task_id, current_group)
    if group_state == "still_running":
        return "still_running"
    if group_state == "group_done_fail":
        state["any_group_fail"] = True

    # 推进到下一 group
    groups = state.get("groups") or [current_group]
    current_group_idx = groups.index(current_group) if current_group in groups else -1
    next_group = None
    for i in range(current_group_idx + 1, len(groups)):
        if groups[i]:
            next_group = groups[i]
            break
    if next_group and len(next_group) >= 2:
        # 启动下一 group
        plan_file = ws / ".ccc" / "plans" / f"{task_id}.plan.md"
        if plan_file.exists():
            plan_content = plan_file.read_text(encoding="utf-8")
            # 拿当前 timeout
            timeout_s = 600
            phases = _load_phases(task_id)
            if phases:
                timeout_s = _lookup_phase_timeout(task_id, phases)
            label = _ws_label(ws)
            ok, meta = _launch_parallel_group(
                ws,
                task_id,
                next_group,
                plan_content,
                timeout_s,
                label,
            )
            if ok:
                state["current_group"] = next_group
                state["phase_meta"] = meta
                engine_log(
                    f"[parallel][next-group] {task_id} 下一 group {next_group} 启动"
                )
                return "still_running"
            engine_log(f"[parallel][warn] {task_id} 下一 group 启动失败，标 group fail")
            state["any_group_fail"] = True

    # 全部 group 完成（或后续 group 启不动）
    any_fail = bool(state.get("any_group_fail"))
    _parallel_phases.pop(key, None)
    pids_dir = ws / ".ccc" / "pids"
    try:
        (pids_dir / f"{task_id}.done").write_text("ok")
        (pids_dir / f"{task_id}.exitcode").write_text("1" if any_fail else "0")
    except OSError as exc:
        engine_log(f"[parallel][marker-write] {task_id} 写完成 marker 失败: {exc}")
    label = _ws_label(ws)
    engine_log(
        f"[parallel][task-done] [{label}] {task_id} 全部 group 完成 (any_fail={any_fail})"
    )
    return "task_complete_fail" if any_fail else "task_complete_ok"


def _parallel_task_marker_to_result(ws: Path, task_id: str) -> dict:
    """类似 dev_role_check_complete: 把并行 task 的 done/exitcode 映射成 status dict。"""
    ws = ws.resolve()
    pids_dir = ws / ".ccc" / "pids"
    done_path = pids_dir / f"{task_id}.done"
    exit_path = pids_dir / f"{task_id}.exitcode"
    if not done_path.exists():
        return {"status": "running", "retry": 0}
    try:
        ec = int(exit_path.read_text().strip()) if exit_path.exists() else 1
    except (ValueError, OSError):
        ec = 1
    if ec == 0:
        return {"status": "success", "retry": 0}
    return {"status": "failed", "retry": 0}


def _reset_parallel_disabled_after_tick() -> None:
    """tick 边界 reset PHASE_PARALLEL_DISABLED（fallback 只对当次 tick 生效）。"""
    global PHASE_PARALLEL_DISABLED
    PHASE_PARALLEL_DISABLED = False


def engine_loop(workspaces: list[Path]) -> None:
    global MAX_RETRY
    """引擎主循环：多 workspace 轮询，全局 MAX_CONCURRENT 共享。"""
    global _engine_shutdown

    program_dir = Path.home() / "program"
    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"CCC Engine 启动 ({len(workspaces)} workspace)")
    engine_log(f"  workspaces={labels}")
    engine_log(
        f"  poll_interval={cfg.engine_poll_interval}s, idle_sleep={cfg.engine_idle_sleep}s"
    )
    engine_log(f"  max_retry={MAX_RETRY}, max_concurrent={MAX_CONCURRENT}")

    active_tasks: dict[str, dict] = {}
    iteration = 0

    for ws in workspaces:
        _recover_tasks(ws, active_tasks)

    while not _engine_shutdown:
        iteration += 1
        tick_start = time.time()
        any_active = bool(active_tasks)

        first_task = next(iter(active_tasks.values()), {})
        first_task_id = first_task.get("task_id")
        first_task_ws = first_task.get("workspace")
        current_phase = None
        if first_task_id and first_task_ws:
            try:
                _activate_workspace(first_task_ws)
                current_phase = _current_running_phase(first_task_id)
            except Exception as exc:
                engine_log(f"stats phase lookup failed for {first_task_id}: {exc}")
        _update_stats(
            active_count=len(active_tasks),
            current_task=first_task_id,
            current_phase=current_phase,
            phase_status="running" if any_active else "done",
            workspace_name=first_task_ws.name if first_task_ws else None,
        )

        try:
            completed_tasks: list[str] = []
            if active_tasks:
                # v0.31+: hang 自动重启（Phase 4 + Phase 5 联合投递）
                # Phase 4 先检测并写 .hung marker，Phase 5 再消费 marker 触发
                # kill+stash+relaunch，最后再做完成判定。
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_and_mark_hung(ws, active_tasks)
                    _run_hang_auto_restart(ws, active_tasks)
                for key, info in list(active_tasks.items()):
                    ws = info["workspace"]
                    tid = info["task_id"]
                    label = _ws_label(ws, program_dir)
                    _activate_workspace(ws)
                    mode = info.get("mode", "serial")
                    if mode == "parallel":
                        # v0.28.2: 并行 task 走专用检查器
                        par_state = _check_parallel_task_complete(ws, tid)
                        if par_state == "still_running":
                            if iteration % 60 == 0:
                                engine_log(f"[parallel] [{label}] {tid} 执行中")
                            any_active = True
                            continue
                        # task_complete_ok / task_complete_fail → 包装成 result
                        if par_state == "task_complete_ok":
                            result = {"status": "success", "retry": 0}
                        else:
                            result = {"status": "failed", "retry": 0}
                    else:
                        result = dev_role_check_complete(tid)
                    status = result.get("status", "unknown")
                    complexity = info.get("complexity", "medium")

                    if status == "running":
                        if iteration % 60 == 0:
                            engine_log(f"[{label}] {tid} 执行中")
                        any_active = True
                        continue

                    if _handle_task_result(ws, tid, result, complexity):
                        completed_tasks.append(key)

                for key in completed_tasks:
                    active_tasks.pop(key, None)
                # tick 边界重置 fallback 标志
                _reset_parallel_disabled_after_tick()

            # 每 6 轮（~60s）跑一次 stale check + testing 流转 + 统计聚合
            if iteration % 6 == 0:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _store = _get_store(ws)
                    _check_stale(ws)
                    _retry_abnormal_dev_failures(ws)
                    test_tasks = _store.list_tasks("testing")
                    if test_tasks:
                        label = _ws_label(ws)
                        engine_log(
                            f"[{label}] testing 列有 {len(test_tasks)} 个任务，跑 reviewer+tester 门禁"
                        )
                        _run_testing_tasks_gate(ws)
                    # v0.30: 定期统计聚合（即使系统忙）
                    try:
                        aggregate_stats(ws)
                        # v0.31: 自适应调参（读 summary.json → 调整 timeout/retry）
                        try:
                            summary = load_summary(ws)
                            if summary and summary.get("total_events", 0) > 5:
                                task_stats = summary.get("task_stats", {})
                                total = task_stats.get("total", 0)
                                failed = task_stats.get("failed", 0)
                                if total > 0:
                                    fail_rate = failed / total
                                    if fail_rate > 0.4 and MAX_RETRY < 5:
                                        engine_log(
                                            f"[auto-tune] fail_rate={fail_rate:.0%}, "
                                            f"MAX_RETRY={MAX_RETRY} (adjusting)"
                                        )
                                        MAX_RETRY = min(MAX_RETRY + 1, 5)
                                    elif fail_rate < 0.1 and MAX_RETRY > 2:
                                        engine_log(
                                            f"[auto-tune] fail_rate={fail_rate:.0%}, "
                                            f"MAX_RETRY={MAX_RETRY} (reducing)"
                                        )
                                        MAX_RETRY = max(MAX_RETRY - 1, 2)
                        except Exception as exc:
                            engine_log(f"[auto-tune] error: {exc}")
                    except Exception as exc:
                        engine_log(
                            f"[stats] periodic aggregate error for {ws.name}: {exc}"
                        )
            ws_first_running: dict[str, str | None] = {}
            ws_active_counts: dict[str, int] = {}
            for info in active_tasks.values():
                ws_key = str(info["workspace"])
                if ws_key not in ws_first_running:
                    ws_first_running[ws_key] = info["task_id"]
                ws_active_counts[ws_key] = ws_active_counts.get(ws_key, 0) + 1
            for ws in workspaces:
                ws_key = str(ws)
                running_task_id = ws_first_running.get(ws_key)
                ws_count = ws_active_counts.get(ws_key, 0)
                ws_pids = _get_running_pids(ws) if running_task_id else []
                _write_heartbeat(ws, running_task_id, ws_count, ws_pids)

            while len(active_tasks) < MAX_CONCURRENT and not _engine_shutdown:
                # v1.0: planned 优先（dev_role），无 planned 才 backlog（product_role）
                # 避免 60+ backlog 阻塞 dev_role 永远不启动（B1）
                did_something = False
                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _try_launch_planned(ws, active_tasks):
                        did_something = True
                        any_active = True
                        break

                if did_something:
                    # B4: 不 continue，让本轮也处理 backlog，否则有 planned 时 backlog 永不处理
                    pass

                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _process_backlog(ws):
                        did_something = True
                        any_active = True

                if not did_something:
                    break

            if not active_tasks:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_stale(ws)
                    # 空闲时立即处理 testing 任务
                    _store2 = _get_store(ws)
                    test_tasks = _store2.list_tasks("testing")
                    if test_tasks:
                        label = _ws_label(ws)
                        engine_log(
                            f"[{label}] idle: testing 列有 {len(test_tasks)} 个任务，跑 reviewer+tester 门禁"
                        )
                        _run_testing_tasks_gate(ws)
                    _write_heartbeat(ws, None, 0, [])

                    if _audit_should_run(str(ws)):
                        label = _ws_label(ws, program_dir)
                        engine_log(f"[{label}] 触发 audit_role（全项目扫描）")
                        try:
                            ccc_board.audit_role(workspace=str(ws))
                        except Exception as exc:
                            engine_log(f"[{label}] audit_role 异常: {exc}")

                    # backlog+planned 为空时立即补充（绕过 2h 间隔，5min 冷却）
                    _auto_replenish_backlog(ws, _store2, program_dir)

                    _retry_abnormal_dev_failures(ws)
                    _check_new_reviews(ws)

                    # v0.30: 空闲时聚合统计 → 反馈回路（学习飞轮）
                    try:
                        summary = aggregate_stats(ws)
                        if summary:
                            insights = summary.get("perf_insights", [])
                            recs = summary.get("recommendations", [])
                            for ins in insights:
                                if ins.get("severity") == "warning":
                                    engine_log(
                                        "[stats] %s — %s",
                                        ws.name,
                                        ins.get("label", ""),
                                    )
                            for rec in recs:
                                if rec.get("action") != "system_healthy":
                                    engine_log(
                                        "[stats-recommend] %s: %s",
                                        rec.get("action", "?"),
                                        rec.get("suggestion", ""),
                                    )
                    except Exception as exc:
                        engine_log(f"[stats] aggregate error for {ws.name}: {exc}")

            if not any_active:
                time.sleep(cfg.engine_tick_interval)
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

    engine_log("收到关闭信号，停止接收新任务")


def _wait_tick(tick_start: float) -> None:
    elapsed = time.time() - tick_start
    remaining = cfg.engine_poll_interval - elapsed
    if remaining > 0:
        time.sleep(min(remaining, cfg.engine_poll_interval))


def _audit_should_run(workspace: str, interval_hours: int = 2) -> bool:
    from datetime import datetime as _dt

    ws_slug = Path(workspace).name if workspace else "CCC"
    last_run_file = Path.home() / ".ccc" / f"audit-last-run.{ws_slug}.json"
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
    from datetime import datetime as _dt

    try:
        data = json.loads(old_file.read_text())
        last = _dt.fromisoformat(data["last_run"].replace("Z", "+00:00"))
        now = _dt.now(timezone.utc)
        hours = (now - last).total_seconds() / 3600
        return hours >= interval_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def _retry_abnormal_dev_failures(ws: Path) -> None:
    """扫描 abnormal 中因 dev 重试耗尽而隔离的任务，冷却后自动移回 planned 重试。

    避免手动操作，让因 transient 错误（网络、依赖安装、opencode 临时故障）
    而失败的任务有机会自动恢复。最大自动重试 3 次（与 dev 的 max_retry 独立）。
    """
    from datetime import datetime as _dt
    import json as _json

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    now = _dt.now(timezone.utc)
    # auto_retry 计数器文件（每个 ws 一个，记录 task_id→重试次数）
    retry_counter_file = ws / ".ccc" / ".dev_auto_retry.json"
    retry_counts: dict[str, int] = {}
    if retry_counter_file.exists():
        try:
            retry_counts = _json.loads(retry_counter_file.read_text())
        except (_json.JSONDecodeError, OSError):
            retry_counts = {}
    MAX_AUTO_RETRY = 3
    COOLDOWN_MINUTES = 15
    moved_tasks: list[str] = []

    for task in store.list_tasks("abnormal"):
        tid = task["id"]
        reason = task.get("note", "")
        # 仅处理 dev 执行失败类（"重试N次全部失败" 特征）
        if "重试" not in reason and "all_failed_or_skipped" not in reason:
            continue
        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            minutes_since = (now - updated).total_seconds() / 60
        except (ValueError, TypeError):
            continue
        if minutes_since < COOLDOWN_MINUTES:
            continue  # 冷却中
        auto_retried = retry_counts.get(tid, 0)
        if auto_retried >= MAX_AUTO_RETRY:
            continue  # 超过最大自动重试次数
        # 移回 planned
        try:
            task_json = _json.loads(
                (ws / ".ccc/board/abnormal" / f"{tid}.jsonl").read_text()
            )
            task_json["status"] = "planned"
            task_json["updated_at"] = now_iso()
            task_json["note"] = (
                f"auto-retry #{auto_retried + 1}/{MAX_AUTO_RETRY}: {reason[:80]}"
            )
            planned_dir = ws / ".ccc/board/planned"
            planned_dir.mkdir(parents=True, exist_ok=True)
            (planned_dir / f"{tid}.jsonl").write_text(
                _json.dumps(task_json, ensure_ascii=False) + "\n"
            )
            # 删 abnormal
            (ws / ".ccc/board/abnormal" / f"{tid}.jsonl").unlink()
            retry_counts[tid] = auto_retried + 1
            store.update_index()
            engine_log(
                f"[{label}] auto-retry #{auto_retried + 1}/{MAX_AUTO_RETRY}: {tid} "
                f"(冷却 {minutes_since:.0f}min) → planned"
            )
            moved_tasks.append(tid)
        except Exception as e:
            _log.warning("auto-retry failed for %s: %s", tid, e)

    try:
        retry_counter_file.write_text(
            _json.dumps(retry_counts, ensure_ascii=False) + "\n"
        )
    except OSError:
        pass

    # v0.31: 每次移回前检查 lessons 是否有建议
    try:
        from _lessons import get_recent_lessons

        recent = get_recent_lessons(ws)
        for task_id in moved_tasks:
            for lesson in recent:
                if lesson.get("task_id") == task_id and not lesson.get("fixed"):
                    _log.info(
                        "[lessons-reapply] %s: %s",
                        task_id,
                        lesson.get("error", "")[:80],
                    )
    except Exception:
        pass


def _check_new_reviews(ws: Path) -> None:
    try:
        from _review_validator import scan_review_dir

        results = scan_review_dir(str(ws))
        label = _ws_label(ws)
        for r in results:
            if not r.get("valid"):
                fname = Path(r.get("file", "?")).name
                errs = "; ".join(r["errors"][:3])
                engine_log(f"[{label}] 🔴 报告格式错误 {fname}: {errs}")
    except ImportError as e:
        _log.warning("_review_validator unavailable, skipping review scan: %s", e)
    except Exception as exc:
        engine_log(f"review 校验异常: {exc}")


def _check_stale(ws: Path) -> None:
    from datetime import datetime as _dt

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    now = _dt.now(timezone.utc)
    for task in store.list_tasks("in_progress"):
        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            hours_stale = (now - updated).total_seconds() / 3600
            if hours_stale > cfg.max_stale_hours:
                tid = task["id"]
                reason = (
                    f"engine: in_progress 滞留 {hours_stale:.1f}h "
                    f"(阈值 {cfg.max_stale_hours}h)"
                )
                cur_phase = _current_running_phase(tid)
                _quarantine_with_notify(ws, tid, reason, store, phase=cur_phase)
                engine_log(
                    f"[{label}] stale: {tid} in_progress 滞留 "
                    f"{hours_stale:.1f}h → abnormal"
                )
        except (ValueError, TypeError) as e:
            _log.warning(
                "stale task timestamp parse failed for %s: %s", task.get("id"), e
            )
    try:
        store.cleanup_events(max_days=30)
    except Exception as e:
        _log.warning("events TTL cleanup failed: %s", e, exc_info=True)


def _kill_pid(pid: int) -> bool:
    """发 SIGTERM，等 5s，仍存活则 SIGKILL。返回是否最终被 kill。"""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        _log.warning("kill %d permission denied", pid)
        return False
    except OSError as exc:
        _log.warning("kill %d SIGTERM failed: %s", pid, exc)
        return False
    time.sleep(5)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return True  # 进程存在但没权限（macOS root-owned）
    except OSError:
        return True
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError as exc:
        _log.warning("kill %d SIGKILL failed: %s", pid, exc)
        return False
    return True


def _git_stash_ws(ws: Path, tid: str, phase_num: int) -> bool:
    """cd ws && git stash push -m 'ccc-auto-stash: ...'。返回是否成功。"""
    try:
        result = subprocess.run(
            ["git", "stash", "push", "-m", f"ccc-auto-stash: {tid} phase {phase_num}"],
            cwd=str(ws),
            capture_output=True,
            timeout=30,
            text=True,
        )
    except subprocess.TimeoutExpired:
        _log.warning("git stash timed out for %s", tid)
        return False
    except OSError as exc:
        _log.warning("git stash failed for %s: %s", tid, exc)
        return False
    if result.returncode != 0:
        _log.warning(
            "git stash non-zero exit for %s: rc=%d stderr=%s",
            tid,
            result.returncode,
            (result.stderr or "")[:200],
        )
        return False
    return True


def _check_and_mark_hung(ws: Path, active_tasks: dict[str, dict]) -> None:
    """扫描 active_tasks 中的 running phase，检测 hung 条件并写 .hung marker。

    Phase 4 of executor-hang-detection plan（与 Phase 5 `_run_hang_auto_restart`
    配对）。同一 tick 内 Phase 4 先跑、Phase 5 后跑：

      Phase 4 (本函数): 检测 → 写 `.ccc/pids/<subid>.hung`（JSON）
      Phase 5 (_run_hang_auto_restart): 读 .hung → kill + git stash + relaunch

    判定条件（全部满足才写 marker）：
      1. PID 存活（`os.kill(pid, 0)`，已退出抛 ProcessLookupError → 跳过）
      2. CPU 0%（`ps -p PID -o %cpu=`，非 0 → 跳过，进程仍在工作）
      3. 运行时长 > _HANG_CHECK_INTERVAL_SEC（`info["started_at"]`，不足 → 跳过）

    排除项：
      - 已存在 `.hung` → 不重复标记
      - 已存在 `.done` → 任务已正常完成（race-safe）
    """
    from datetime import datetime as _dt

    _activate_workspace(ws)
    label = _ws_label(ws)
    pids_dir = ws / ".ccc" / "pids"
    now = _dt.now(timezone.utc)

    for key, info in list(active_tasks.items()):
        if info.get("workspace") != ws:
            continue
        tid = info["task_id"]
        try:
            cur_phase = _current_running_phase(tid)
        except Exception as exc:
            engine_log(f"[{label}] hang-detect: 读 {tid} current phase 失败: {exc}")
            continue
        if cur_phase is None or cur_phase <= 0:
            continue

        subid = _phase_market_subid(tid, cur_phase)
        hung_path = pids_dir / f"{subid}.hung"
        done_path = pids_dir / f"{subid}.done"
        pid_path = pids_dir / f"{subid}.pid"

        # 已标记或已完成 → 跳过
        if hung_path.is_file():
            continue
        if done_path.is_file():
            continue

        # 读 PID
        if not pid_path.is_file():
            continue
        try:
            pid = int(pid_path.read_text().strip())
        except (ValueError, OSError) as exc:
            engine_log(f"[{label}] hang-detect: {tid} 读 PID 失败: {exc}")
            continue
        if pid <= 0:
            continue

        # PID 存活检查
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            # 进程存在但没权限（macOS root-owned），视为仍存活
            pass
        except OSError as exc:
            engine_log(f"[{label}] hang-detect: {tid} PID={pid} 检查异常: {exc}")
            continue

        # 运行时长检查
        started_str = info.get("started_at", "")
        if not started_str:
            continue
        try:
            started = _dt.fromisoformat(str(started_str).replace("Z", "+00:00"))
            elapsed = (now - started).total_seconds()
        except (ValueError, TypeError) as exc:
            engine_log(f"[{label}] hang-detect: {tid} started_at 解析失败: {exc}")
            continue
        if elapsed < _HANG_CHECK_INTERVAL_SEC:
            continue

        # CPU 检查（仅在存活 + 足够久的 phase 上跑）
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu="],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            engine_log(f"[{label}] hang-detect: {tid} ps 超时，跳过本次")
            continue
        except OSError as exc:
            engine_log(f"[{label}] hang-detect: {tid} ps 异常: {exc}")
            continue
        if result.returncode != 0:
            # 进程刚退出，ps 返回非 0 → 不算 hung
            continue
        try:
            cpu = float(result.stdout.strip())
        except ValueError:
            engine_log(
                f"[{label}] hang-detect: {tid} ps 输出无法解析: {result.stdout!r}"
            )
            continue
        if cpu > 0.0:
            continue

        # 全部条件满足 → 写 .hung marker
        marker = {
            "task_id": tid,
            "phase": cur_phase,
            "pid": pid,
            "cpu": cpu,
            "elapsed_sec": int(elapsed),
            "detected_at": now_iso(),
        }
        try:
            hung_path.write_text(json.dumps(marker, ensure_ascii=False) + "\n")
        except OSError as exc:
            engine_log(f"[{label}] hang-detect: {tid} 写 .hung 失败: {exc}")
            continue

        _log_stats(
            ws,
            "hang_detected",
            tid,
            phase=cur_phase,
            pid=pid,
            cpu=cpu,
            elapsed_sec=int(elapsed),
        )
        engine_log(
            f"[{label}] hang-detect: {tid} phase {cur_phase} PID={pid} "
            f"CPU={cpu:.1f}% 运行时长={int(elapsed)}s → 标记 .hung"
        )


def _run_hang_auto_restart(ws: Path, active_tasks: dict[str, dict]) -> None:
    """扫描 active_tasks 中的 hung phase 并自动重启（v0.31+）。

    检测 active_tasks 中每个 task 的当前 phase 是否已被 Phase 4
    （executor-hang-detection）标记为 hung（.ccc/pids/<subid>.hung）。

    如标记存在：
      1. 解析 subid → 读 .pid 文件拿到 PID
      2. kill -TERM → 5s 后存活则 kill -KILL
      3. cd ws && git stash push -m 'ccc-auto-stash: <tid> phase <n>'
      4. 清理 .hung 文件
      5. dev_role_relaunch(tid) 用同一 plan 重启
      6. 更新 _hang_retry_counter，超限则 quarantine + notify
    """
    global _hang_retry_counter

    _activate_workspace(ws)
    label = _ws_label(ws)
    pids_dir = ws / ".ccc" / "pids"

    for key, info in list(active_tasks.items()):
        if info.get("workspace") != ws:
            continue
        tid = info["task_id"]
        try:
            cur_phase = _current_running_phase(tid)
        except Exception as exc:
            engine_log(f"[{label}] hang-auto: 读 {tid} current phase 失败: {exc}")
            continue
        if cur_phase is None or cur_phase <= 0:
            continue

        subid = _phase_market_subid(tid, cur_phase)
        hung_path = pids_dir / f"{subid}.hung"
        if not hung_path.is_file():
            continue

        retries = _hang_retry_counter.get(key, 0)
        engine_log(
            f"[{label}] hang-auto: {tid} phase {cur_phase} 标记 hung "
            f"(auto-retry {retries + 1}/{_MAX_HANG_RETRY})"
        )

        # 1) 读 PID
        pid_path = pids_dir / f"{subid}.pid"
        pid: int | None = None
        if pid_path.is_file():
            try:
                pid = int(pid_path.read_text().strip())
            except (ValueError, OSError):
                pid = None
        else:
            engine_log(
                f"[{label}] hang-auto: {tid} 缺 {pid_path.name}（可能已退出），跳过 kill"
            )

        # 2) kill
        if pid is not None and pid > 0:
            if _kill_pid(pid):
                engine_log(f"[{label}] hang-auto: {tid} PID={pid} 已 kill")
            else:
                engine_log(f"[{label}] hang-auto: {tid} PID={pid} kill 失败，继续")

        # 3) git stash
        if not _git_stash_ws(ws, tid, cur_phase):
            engine_log(f"[{label}] hang-auto: {tid} git stash 失败，跳过 restart")
            # 仍然清理 hung 标记避免无限循环
            try:
                hung_path.unlink()
            except OSError:
                pass
            continue

        # 4) 清理 .hung
        try:
            hung_path.unlink()
        except OSError as exc:
            engine_log(f"[{label}] hang-auto: 清理 {hung_path.name} 失败: {exc}")

        # 5) 重启或超限 quarantine
        if retries >= _MAX_HANG_RETRY:
            reason = f"hang auto-restart 耗尽（{_MAX_HANG_RETRY} 次）— {tid} phase {cur_phase}"
            engine_log(f"[{label}] hang-auto: {tid} 超限 → abnormal")
            _quarantine_with_notify(ws, tid, reason, phase=cur_phase)
            # 不增加计数，避免 dict 无限增长
            _hang_retry_counter[key] = retries
            continue

        try:
            _activate_workspace(ws)
            result = dev_role_relaunch(tid)
        except Exception as exc:
            engine_log(f"[{label}] hang-auto: {tid} relaunch 异常: {exc}")
            result = {"ok": False}

        _hang_retry_counter[key] = retries + 1
        if result.get("ok"):
            engine_log(
                f"[{label}] hang-auto: {tid} phase {cur_phase} 已重启 "
                f"(retry {retries + 1}/{_MAX_HANG_RETRY})"
            )
        else:
            engine_log(f"[{label}] hang-auto: {tid} relaunch 返回非 ok: {result}")


def _get_running_pids(ws: Path) -> list[int]:
    """扫描 .ccc/pids/ 目录，返回没有对应 .done 标记的 PID 列表。"""
    pids_dir = ws / ".ccc" / "pids"
    if not pids_dir.is_dir():
        return []
    result: list[int] = []
    for f in sorted(pids_dir.iterdir()):
        if f.suffix != ".pid":
            continue
        subid = f.stem
        if (pids_dir / f"{subid}.done").exists():
            continue
        try:
            pid = int(f.read_text().strip())
            if pid > 0:
                result.append(pid)
        except (ValueError, OSError):
            pass
    return result


def _write_heartbeat(
    ws: Path,
    running_task_id: str | None,
    active_task_count: int = 0,
    running_pids: list[int] | None = None,
) -> None:
    ws = ws.resolve()
    hb = {
        "workspace": str(ws),
        "running": running_task_id or None,
        "active_task_count": active_task_count,
        "running_pids": running_pids or [],
        "timestamp": now_iso(),
    }
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    try:
        hb_file.write_text(json.dumps(hb, ensure_ascii=False) + "\n")
    except OSError as e:
        _log.warning("engine heartbeat write failed for %s: %s", ws, e)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="CCC Engine — multi-workspace scheduler"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_STATS_PORT,
        help=f"Stats HTTP 端点端口（默认 {_STATS_PORT}）",
    )
    args = parser.parse_args(argv)

    program_dir = Path.home() / "program"
    workspaces = _discover_workspaces()
    if not workspaces:
        engine_log("未找到任何 workspace（需 ~/program/*/.ccc/board/）")
        sys.exit(1)

    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"发现 {len(workspaces)} 个 workspace: {labels}")

    def _handle_sigterm(signum, frame):
        global _engine_shutdown
        if _engine_shutdown:
            return
        _engine_shutdown = True
        engine_log("收到 SIGTERM, 优雅关闭中...")

    signal.signal(signal.SIGTERM, _handle_sigterm)

    _run_stats_server(args.port)

    try:
        engine_loop(workspaces)
    except KeyboardInterrupt:
        engine_log("Engine 关闭")
    except SystemExit:
        _log.debug("engine exiting via SystemExit")
    _engine_shutdown = True
    engine_log("Engine 终止")


# ── Stats HTTP Endpoint（plan: engine-stats-endpoint） ──
def _read_engine_version() -> str:
    try:
        return (_script_dir.parent / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


_ENGINE_VERSION = _read_engine_version()
_stats_started_at: float | None = time.time()
_stats_lock = threading.Lock()
_stats_data: dict = {
    "uptime_sec": 0.001,
    "current_task": None,
    "current_phase": None,
    "phase_status": "pending",
    "in_progress_count": 0,
    "engine_version": _ENGINE_VERSION,
    "last_tick_at": None,
    "workspace": Path.cwd().name,
}


def _update_stats(
    active_count: int,
    current_task: str | None = None,
    current_phase: int | None = None,
    phase_status: str | None = None,
    workspace_name: str | None = None,
) -> None:
    global _stats_started_at
    now = now_iso()
    now_ts = time.time()
    with _stats_lock:
        if _stats_started_at is None:
            _stats_started_at = now_ts
            _stats_data["uptime_sec"] = 0
        else:
            _stats_data["uptime_sec"] = max(0.001, now_ts - _stats_started_at)
        _stats_data["current_task"] = current_task
        _stats_data["current_phase"] = current_phase
        _stats_data["phase_status"] = phase_status or (
            "running" if active_count else "done"
        )
        _stats_data["in_progress_count"] = active_count
        _stats_data["last_tick_at"] = now
        if workspace_name:
            _stats_data["workspace"] = workspace_name


class _StatsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        engine_log(
            "[stats-api] %s - [%s] %s",
            self.address_string(),
            self.log_date_time_string(),
            format % args,
        )

    def do_GET(self):
        if self.path == "/api/stats":
            try:
                with _stats_lock:
                    payload = json.dumps(_stats_data, ensure_ascii=False).encode(
                        "utf-8"
                    )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as exc:
                engine_log(f"[stats-api] 响应失败: {exc}")
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception:
                    pass
        else:
            self.send_response(404)
            self.end_headers()


def _stats_snapshot() -> dict:
    """HTTP 线程用的快照方法：与 _update_stats 共享锁。"""
    with _stats_lock:
        return dict(_stats_data)


def _run_stats_server(port: int) -> None:
    """在独立线程跑轻量 HTTP 服务，仅 127.0.0.1。"""
    try:
        server = HTTPServer(("127.0.0.1", port), _StatsHandler)
    except OSError as exc:
        engine_log(f"Stats HTTP 启动失败 (port={port}): {exc}")
        return
    engine_log(f"Stats HTTP 服务启动在 http://127.0.0.1:{port}/api/stats")

    def _serve():
        try:
            while not _engine_shutdown:
                server.handle_request()
        except Exception as exc:
            engine_log(f"Stats HTTP 服务异常: {exc}")
        finally:
            try:
                server.server_close()
            except Exception:
                pass
            engine_log("Stats HTTP 服务关闭")

    t = threading.Thread(target=_serve, name="ccc-stats-http", daemon=True)
    t.start()


if __name__ == "__main__":
    main()

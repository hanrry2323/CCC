#!/usr/bin/env python3
"""ccc-engine.py — CCC 多 workspace 并行执行引擎 (v0.28.1+)

替代「每 workspace 一个 engine 进程」模式。
单进程扫描 ~/program/* 下所有含 .ccc/board/ 的项目，全局 MAX_CONCURRENT=3 共享并发池。

使用方式:
  python3 ccc-engine.py

退出:
  Ctrl+C 或 SIGTERM → 优雅关闭
"""

import json
import os
import signal
import subprocess
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

# ccc-board 在 import 时会 eager 绑定 ROOT；默认 workspace 供首次加载
os.environ.setdefault("CCC_WORKSPACE", str(_script_dir.parent))

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

_engine_shutdown = False
_MAX_PRODUCT_RETRIES = 3
MAX_CONCURRENT = 3

_stores: dict[str, FileBoardStore] = {}


def now_iso() -> str:
    return _utils_now_iso()


def engine_log(msg: str) -> None:
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
    ws: Path, tid: str, reason: str, store: FileBoardStore | None = None
) -> None:
    """移入 abnormal 并触发桌面通知。"""
    _activate_workspace(ws)
    if store is None:
        store = _get_store(ws)
    store.quarantine(tid, reason)
    _log_stats(ws, "quarantine", tid, reason=reason)
    _ccc_notify("CCC", f"任务 {tid} 进入异常状态，原因：{reason}")
    store.update_index()


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
            timeout=600,
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


def _run_reviewer_tester_gate(ws: Path, tid: str) -> bool:
    """reviewer verdict + tester + engine pytest 双门禁。通过才移 verified。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    verdict_ok = False
    for attempt in range(2):
        reviewer_role()
        if _verdict_is_valid(ws, tid):
            verdict_ok = True
            break
        engine_log(
            f"[{label}] {tid} reviewer 未产出有效 verdict (attempt {attempt + 1}/2)"
        )
        _ensure_task_in_testing(store, tid)
        if attempt == 1:
            engine_log(f"[{label}] {tid} reviewer verdict 重试耗尽 → abnormal")
            _quarantine_with_notify(ws, tid, "reviewer 未产出 verdict", store)
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
            _ccc_notify("CCC", f"任务 {tid} pytest 未通过 (exit={exit_code})，已留在 testing")
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
            engine_log(f"[{label}] {tid} complexity=small, 跳过 reviewer+tester → 直通 kb")
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
            ws, tid, f"product_role 连续失败 {fail_count} 次", store
        )
        _ccc_notify(
            "CCC",
            f"product_role 拆分 {tid} 连续失败 {fail_count} 次",
        )
        return True

    engine_log(f"[product] [{label}] backlog 自动拆分: {tid} (此前失败 {fail_count} 次)")
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
                ws, tid, f"product_role 连续失败 {fail_count} 次", store
            )
            _ccc_notify(
                "CCC",
                f"product_role 拆分 {tid} 连续失败 {fail_count} 次",
            )
    return True


def _try_launch_planned(ws: Path, active_tasks: dict[str, dict]) -> bool:
    """从 planned 启动一个 task。返回 True 表示已启动。"""
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
                engine_log(f"[{label}] {tid} 所有 phase 被跳过（依赖失败链），跳过 task 启动")
                continue

        complexity = task.get("complexity", "medium")
        engine_log(f"[{label}] 取新 task: {tid} (complexity={complexity})")
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


def engine_loop(workspaces: list[Path]) -> None:
    """引擎主循环：多 workspace 轮询，全局 MAX_CONCURRENT 共享。"""
    global _engine_shutdown

    program_dir = Path.home() / "program"
    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"CCC Engine 启动 ({len(workspaces)} workspace)")
    engine_log(f"  workspaces={labels}")
    engine_log(f"  poll_interval={cfg.engine_poll_interval}s, idle_sleep={cfg.engine_idle_sleep}s")
    engine_log(f"  max_retry={MAX_RETRY}, max_concurrent={MAX_CONCURRENT}")

    active_tasks: dict[str, dict] = {}
    iteration = 0

    for ws in workspaces:
        _startup_scan_workspace(ws, active_tasks)

    while not _engine_shutdown:
        iteration += 1
        tick_start = time.time()
        any_active = bool(active_tasks)

        try:
            completed_tasks: list[str] = []
            if active_tasks:
                for key, info in list(active_tasks.items()):
                    ws = info["workspace"]
                    tid = info["task_id"]
                    label = _ws_label(ws, program_dir)
                    _activate_workspace(ws)
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


            # 每 6 轮（~60s）跑一次 stale check + testing 流转
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
            ws_first_running: dict[str, str | None] = {}
            for info in active_tasks.values():
                ws_key = str(info["workspace"])
                if ws_key not in ws_first_running:
                    ws_first_running[ws_key] = info["task_id"]
            for ws in workspaces:
                ws_key = str(ws)
                _write_heartbeat(ws, ws_first_running.get(ws_key))

            while len(active_tasks) < MAX_CONCURRENT and not _engine_shutdown:
                did_something = False
                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _process_backlog(ws):
                        did_something = True
                        break

                if did_something:
                    any_active = True
                    continue

                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _try_launch_planned(ws, active_tasks):
                        did_something = True
                        any_active = True
                        break

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
                    _write_heartbeat(ws, None)

                    if _audit_should_run(str(ws)):
                        label = _ws_label(ws, program_dir)
                        engine_log(f"[{label}] 触发 audit_role（全项目扫描）")
                        try:
                            ccc_board.audit_role(workspace=str(ws))
                        except Exception as exc:
                            engine_log(f"[{label}] audit_role 异常: {exc}")

                    _retry_abnormal_dev_failures(ws)
                    _check_new_reviews(ws)

                if not any_active:
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
            task_json = _json.loads((ws / ".ccc/board/abnormal" / f"{tid}.jsonl").read_text())
            task_json["status"] = "planned"
            task_json["updated_at"] = now_iso()
            task_json["note"] = f"auto-retry #{auto_retried + 1}/{MAX_AUTO_RETRY}: {reason[:80]}"
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
        except Exception as e:
            _log.warning("auto-retry failed for %s: %s", tid, e)

    try:
        retry_counter_file.write_text(_json.dumps(retry_counts, ensure_ascii=False) + "\n")
    except OSError:
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
                reason = (
                    f"engine: in_progress 滞留 {hours_stale:.1f}h "
                    f"(阈值 {cfg.max_stale_hours}h)"
                )
                _quarantine_with_notify(ws, task["id"], reason, store)
                engine_log(
                    f"[{label}] stale: {task['id']} in_progress 滞留 "
                    f"{hours_stale:.1f}h → abnormal"
                )
        except (ValueError, TypeError) as e:
            _log.warning("stale task timestamp parse failed for %s: %s", task.get("id"), e)
    try:
        store.cleanup_events(max_days=30)
    except Exception as e:
        _log.warning("events TTL cleanup failed: %s", e, exc_info=True)


def _write_heartbeat(ws: Path, running_task_id: str | None) -> None:
    ws = ws.resolve()
    hb = {
        "workspace": str(ws),
        "running": running_task_id or None,
        "timestamp": now_iso(),
    }
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    try:
        hb_file.write_text(json.dumps(hb, ensure_ascii=False) + "\n")
    except OSError as e:
        _log.warning("engine heartbeat write failed for %s: %s", ws, e)


def main() -> None:
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

    try:
        engine_loop(workspaces)
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

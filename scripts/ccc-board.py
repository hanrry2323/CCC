#!/usr/bin/env python3
"""ccc-board.py — 任务看板核心 (v0.20)

7 角色都通过这个 core 操作 .ccc/board/:
- product: backlog → planned
- dev: planned → in_progress → testing
- reviewer: testing → verified (过 ruff/mypy)
- tester: testing → verified (过 pytest)
- ops: 健康检查 (不动 board)
- kb: verified → released (归档)
- regress: released → backlog (回归回测)

任务流转规则见 .ccc/board/README.md
"""

import argparse
import json
import os
import re
import shlex
import uuid
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from _config import Config
from _board_store import FileBoardStore
from _logger import get_logger
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id

_log = get_logger("board")

# v0.28.0 (L-001): cfg / store 改为 lazy 初始化 — 避免 import 时即建 FileBoardStore
# 触发 mkdir（workspace 路径权限问题会直接挂 import）。
# ROOT / CCC_HOME / BOARD / EVENTS_DIR 仍为 eager（Path() 不触发 I/O，开销可忽略）。
_cfg_instance: Config | None = None
_store_instance: FileBoardStore | None = None


def _get_cfg() -> Config:
    global _cfg_instance
    if _cfg_instance is None:
        _cfg_instance = Config()
    return _cfg_instance


def _get_store() -> FileBoardStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = FileBoardStore(_get_cfg().workspace)
    return _store_instance


def _reset_lazy() -> None:
    """测试辅助：重置 lazy 缓存。"""
    global _cfg_instance, _store_instance
    _cfg_instance = None
    _store_instance = None


# 历史兼容：保留同名 module-level 名称（cfg/store）作为 lazy proxy。
# 旧代码 `cfg.max_retry` / `store.list_tasks(...)` / `cfg.default_timeout` 写法不变。
class _CfgProxy:
    """v0.28.0 (L-001): Config lazy proxy。"""

    def __getattr__(self, name: str):
        return getattr(_get_cfg(), name)


class _StoreProxy:
    """v0.28.0 (L-001): FileBoardStore lazy proxy。"""

    def __getattr__(self, name: str):
        return getattr(_get_store(), name)


cfg = _CfgProxy()
store = _StoreProxy()

ROOT = _get_cfg().workspace
CCC_HOME = _get_cfg().ccc_home
BOARD = ROOT / ".ccc" / "board"
EVENTS_DIR = BOARD / "events"

# 容错参数（从 Config 读取）
MAX_RETRY = cfg.max_retry
MAX_STALE_HOURS = cfg.max_stale_hours
STALE_CHECK_INTERVAL = 6  # ops_role 每次扫描间隔（判断是否该扫描）

# ═══════════════════════════════════════════
# 安全辅助函数
# ═══════════════════════════════════════════


def sanitize_id(tid: str) -> str:
    """净化 task_id：只保留字母、数字、下划线、连字符，防止路径遍历

    v0.28.0 (H-003): 委托 _utils 统一实现。兼容既有调用方。
    """
    return _utils_sanitize_id(tid)


def now_iso() -> str:
    """UTC ISO 8601 时间戳（Z 后缀）

    v0.28.0 (H-003): 委托 _utils 统一实现（之前此文件返回 Asia/Shanghai +08:00，
    与 _board_store.py 的 UTC Z 不一致 → 时间比较时区混淆）。
    """
    return _utils_now_iso()


def _backoff_seconds(retry: int) -> int:
    """指数退避：60 * 2^retry，封顶 3600s（1h）

    retry=0→60s, 1→120s, 2→240s, 3→480s, 4→960s, 5→1920s, 6+→3600s
    """
    return min(60 * (2**retry), 3600)


def _quarantine(task_id: str, reason: str) -> None:
    """将任务移入异常列（委托 FileBoardStore）"""
    store.quarantine(task_id, reason)


def _task_id_exists(task_id: str) -> bool:
    """检查 task_id 是否在任意列中已存在"""
    return store._task_id_exists(task_id)


def create_task(data: dict, column: str = "backlog") -> bool:
    """创建新 task（委托 FileBoardStore）"""
    return store.create_task(data, column=column)


def list_tasks(column: str) -> list[dict]:
    """读某列所有 task（委托 FileBoardStore）"""
    return store.list_tasks(column)


def move_task(task_id: str, from_col: str, to_col: str) -> bool:
    """把 task 从 from_col 挪到 to_col（委托 FileBoardStore）"""
    return store.move_task(task_id, from_col, to_col)


def update_index() -> dict:
    """更新 .ccc/board/index.json 状态总览（委托 FileBoardStore）"""
    return store.update_index()


def _load_timeout(phases_file: Path, default: int = None) -> int:
    """从 phases.jsonl 的第一个 phase 行读 timeout（跳过 schema_version）

    v0.28.0: default 缺省走 cfg.default_timeout（默认 1800）
    """
    if default is None:
        default = cfg.default_timeout
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                phase = json.loads(line)
                if isinstance(phase, list):
                    phase = phase[0] if phase else {}
                if "schema_version" in phase:
                    continue
                to = phase.get("timeout")
                if to is None:
                    return default
                try:
                    from _config import parse_duration
                    return parse_duration(to, default)
                except Exception:
                    return default
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return default


# v0.24: phases.json 加载 + 依赖解析
PHASE_TERMINAL_OK = {"done", "verified", "skipped"}
PHASE_TERMINAL_FAIL = {"failed"}


def _load_phases(task_id: str) -> list[dict]:
    """v0.24: 加载 phases.jsonl 每行一个 phase dict（跳过 schema_version 行）。

    返回按 phase 编号排序的 list，元素为 phase dict。
    文件不存在或解析失败返回空 list。
    """
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        return []
    out: list[dict] = []
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and "schema_version" in obj:
                    continue
                if isinstance(obj, dict) and "phase" in obj:
                    out.append(obj)
    except OSError:
        return []
    out.sort(key=lambda p: p.get("phase", 0))
    return out


def _detect_phase_cycle(phases: list[dict]) -> list[list[int]]:
    """v0.25.1: 检测 phases.json 中的循环依赖。

    用 DFS 三色标记（WHITE=未访问 / GRAY=在栈上 / BLACK=已完成）。
    返回所有循环路径（每条路径是 phase_id 列表）。

    注：函数内静默检测，不抛异常。Engine 在 _resolve_phase_dependencies
    调用时拿到 cycle 列表，把环上 phase 标 skipped + 写 warnings.json。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[int, int] = {p.get("phase"): WHITE for p in phases if p.get("phase") is not None}
    by_id: dict[int, dict] = {p.get("phase"): p for p in phases if p.get("phase") is not None}
    cycles: list[list[int]] = []

    def dfs(node: int, stack: list[int]) -> None:
        color[node] = GRAY
        stack.append(node)
        for dep_id in by_id.get(node, {}).get("depends_on") or []:
            if dep_id not in color:
                continue  # 不存在的依赖由 _resolve_phase_dependencies 处理
            if color[dep_id] == GRAY:
                # 找到循环：截取 stack 从 dep_id 起到 node 的部分
                idx = stack.index(dep_id)
                cycles.append(stack[idx:] + [dep_id])
            elif color[dep_id] == WHITE:
                dfs(dep_id, stack)
        stack.pop()
        color[node] = BLACK

    for pid in list(color.keys()):
        if color[pid] == WHITE:
            dfs(pid, [])

    return cycles


def _resolve_phase_dependencies(phases: list[dict]) -> tuple[set[int], set[int], set[int]]:
    """v0.24: 解析 phase 依赖关系。

    对每个 phase 检查 depends_on 列表中所有前置 phase 的状态：
    - 所有依赖状态 ∈ {done, verified, skipped} → 本 phase 可执行 (executable)
    - 任意依赖状态 ∈ {failed} → 本 phase 跳过 (skipped)
    - 其他依赖未达终态 → 本 phase 阻塞 (blocked）

    v0.25.1: 加循环依赖检测。环上 phase 全部归 skipped（强失败隔离）。

    Returns:
        (executable_phase_ids, blocked_phase_ids, skipped_phase_ids)

    注：本函数只标注新状态（pending → blocked/skipped），已 done/verified/in_progress/failed
    的 phase 不动。Engine 在调用此函数前应已写回 phases.json。
    """
    by_id: dict[int, dict] = {p.get("phase"): p for p in phases if p.get("phase") is not None}

    # v0.25.1: 循环依赖检测 — 环上 phase 强制 skipped
    cycles = _detect_phase_cycle(phases)
    cycle_nodes: set[int] = set()
    for cycle in cycles:
        # cycle = [a, b, c, a] → 环上节点 = {a, b, c}
        cycle_nodes.update(cycle[:-1])

    executable: set[int] = set()
    blocked: set[int] = set()
    skipped: set[int] = set()

    for pid, phase in by_id.items():
        status = phase.get("status", "pending")
        # 已达终态或正在执行 → 不再分类
        if status in PHASE_TERMINAL_OK or status in PHASE_TERMINAL_FAIL or status == "in_progress":
            continue

        # v0.25.1: 环上节点直接 skipped（强失败隔离）
        if pid in cycle_nodes:
            skipped.add(pid)
            continue

        deps = phase.get("depends_on") or []
        if not deps:
            # 无依赖 → 可执行
            executable.add(pid)
            continue

        # 检查所有依赖
        any_failed = False
        any_unresolved = False
        for dep_id in deps:
            dep = by_id.get(dep_id)
            if dep is None:
                # 引用了不存在的 phase → 视为未解析（不强行 fail，留给人工处理）
                any_unresolved = True
                continue
            dep_status = dep.get("status", "pending")
            if dep_status in PHASE_TERMINAL_FAIL:
                any_failed = True
            elif dep_status not in PHASE_TERMINAL_OK:
                any_unresolved = True

        if any_failed:
            skipped.add(pid)
        elif any_unresolved:
            blocked.add(pid)
        else:
            executable.add(pid)

    # v0.25.1: 写 warnings.json（让 ops 看见循环依赖路径）
    if cycles:
        try:
            warnings_file = ROOT / ".ccc" / "warnings.json"
            existing = []
            if warnings_file.exists():
                try:
                    existing = json.loads(warnings_file.read_text())
                    if not isinstance(existing, list):
                        existing = []
                except json.JSONDecodeError:
                    existing = []
            existing.append({
                "type": "phase_cycle",
                "cycles": cycles,
                "detected_at": now_iso(),
            })
            warnings_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
        except OSError as exc:
            _log.debug("write warnings.json (phase_cycle) failed: %s", exc)

    # v0.25.1: 不存在依赖告警（CHANGELOG v0.24.4:97 P1）
    # 检测 depends_on 中引用了不存在的 phase_id；写 warnings.json + L2 通知
    unresolved: dict[int, list[int]] = {}  # phase_id -> [missing dep ids]
    for pid, phase in by_id.items():
        deps = phase.get("depends_on") or []
        for dep_id in deps:
            if dep_id not in by_id:
                unresolved.setdefault(pid, []).append(dep_id)
    if unresolved:
        try:
            warnings_file = ROOT / ".ccc" / "warnings.json"
            existing = []
            if warnings_file.exists():
                try:
                    existing = json.loads(warnings_file.read_text())
                    if not isinstance(existing, list):
                        existing = []
                except json.JSONDecodeError:
                    existing = []
            existing.append({
                "type": "unresolved_dep",
                "missing": {str(k): v for k, v in unresolved.items()},
                "detected_at": now_iso(),
            })
            warnings_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
            # L2 桌面通知（让 dev 立刻看见）
            try:
                subprocess.run(
                    [
                        "bash",
                        str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                        "L2",
                        "phases.json: unresolved dependency detected",
                        f"{len(unresolved)} phase 引用了不存在的 phase_id",
                    ],
                    capture_output=True,
                    timeout=5,
                )
            except Exception as exc:
                _log.debug("ccc-notify.sh L2 unresolved_dep failed: %s", exc)
        except OSError as exc:
            _log.debug("write warnings.json (unresolved_dep) failed: %s", exc)

    return executable, blocked, skipped


def _apply_phase_status_updates(task_id: str, blocked: set[int], skipped: set[int]) -> None:
    """v0.24: 把解析出的 blocked/skipped 状态写回 phases.jsonl。

    双向同步（Engine 每 tick 调用）：
    - pending → skipped（依赖失败）
    - pending → blocked（依赖未满足）
    - blocked → pending（依赖已满足，下一轮可执行）
    已 in_progress/done/verified/failed/skipped 的不碰。

    v0.24.3: 加文件锁 fcntl.flock(LOCK_EX) 防止 Engine 与外部 CLI 并发写竞争。
    """
    import fcntl

    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        return
    try:
        with open(phases_file, "r+") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except (OSError, AttributeError):
                # 非 POSIX 平台或 flock 不可用，降级无锁（保留旧行为）
                pass
            try:
                lines = f.read().splitlines()
            except OSError:
                return
            new_lines: list[str] = []
            changed = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    new_lines.append(line)
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue
                if not isinstance(obj, dict) or "schema_version" in obj:
                    new_lines.append(line)
                    continue
                pid = obj.get("phase")
                status = obj.get("status")
                if status == "pending":
                    if pid in skipped:
                        obj["status"] = "skipped"
                        changed = True
                    elif pid in blocked:
                        obj["status"] = "blocked"
                        changed = True
                elif status == "blocked":
                    # 依赖解除 → 回 pending（让 dev 可以重新拾起）
                    if pid not in blocked and pid not in skipped:
                        obj["status"] = "pending"
                        changed = True
                new_lines.append(json.dumps(obj, ensure_ascii=False))
            if changed:
                payload = "\n".join(new_lines) + "\n"
                f.seek(0)
                f.write(payload)
                f.truncate()
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except (OSError, AttributeError):
                pass
    except OSError:
        return


def _task_all_phases_terminal(task_id: str) -> bool:
    """v0.24: 检查 task 的所有 phase 是否都达终态（done/verified/skipped/failed）。

    Engine 用：task 进入 verified/released 前确认 phase 都结束；如果有 phase
    因依赖失败被 skipped，整体 task 也算结束。
    """
    phases = _load_phases(task_id)
    if not phases:
        return False  # 无 phases 文件 = 旧格式任务，不算 v0.24 phase 流程
    for p in phases:
        st = p.get("status", "pending")
        if st not in (PHASE_TERMINAL_OK | PHASE_TERMINAL_FAIL | {"blocked"}):
            return False
    return True


def _current_running_phase(task_id: str) -> int:
    """v0.24: 找 task 当前正在跑的 phase 编号（status=in_progress 的 phase）。

    没有 in_progress phase 时返回 1（兼容旧 v0.23 行为，task-p1 默认）。
    """
    phases = _load_phases(task_id)
    for p in phases:
        if p.get("status") == "in_progress":
            return p.get("phase", 1)
    # 无 in_progress → 取 pending/blocked 中第一个（按 phase 编号）
    candidates = [p for p in phases if p.get("status") in ("pending", "blocked")]
    if candidates:
        return candidates[0].get("phase", 1)
    return 1


def _mark_phase_failed(task_id: str, phase_id: int) -> None:
    """v0.24: 标记某个 phase 为 failed（quarantine 时调用）。

    仅当 phase 还在 pending/blocked/in_progress 时才改为 failed；
    已 done/verified/skipped/failed 不动。
    """
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        return
    try:
        lines = phases_file.read_text().splitlines()
    except OSError:
        return
    new_lines: list[str] = []
    changed = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue
        if not isinstance(obj, dict) or "schema_version" in obj:
            new_lines.append(line)
            continue
        if obj.get("phase") == phase_id:
            current = obj.get("status")
            if current in ("done", "verified", "skipped", "failed"):
                new_lines.append(line)
                continue
            obj["status"] = "failed"
            changed = True
        new_lines.append(json.dumps(obj, ensure_ascii=False))
    if changed:
        phases_file.write_text("\n".join(new_lines) + "\n")


PHASE_MAX_ENGINE_ITER = 5  # v0.25.1: 多轮 tick 不收敛时强制 failed


def _check_phase_failures(task_id: str) -> dict:
    """v0.24: 检查 task 的 phase 失败传染，更新下游 skipped 状态。

    流程：
    1. 加载 phases
    2. 跑 _resolve_phase_dependencies 解析 executable/blocked/skipped
    3. 写回 blocked/skipped（依赖解除的 blocked → pending）
    4. v0.25.1: 多轮 tick 不收敛（>= PHASE_MAX_ENGINE_ITER）→ 强收敛
       （pending/blocked 标 failed/skipped）
    5. 返回 {"executable": [...], "blocked": [...], "skipped": [...],
            "all_terminal": bool, "all_failed_or_skipped": bool, "engine_iter": int,
            "force_converged": bool}

    Engine 在每次 dev 完成后调用一次，让失败传染链路在多轮 tick 中收敛。
    """
    phases = _load_phases(task_id)
    if not phases:
        return {"executable": [], "blocked": [], "skipped": [],
                "all_terminal": False, "all_failed_or_skipped": False,
                "engine_iter": 0, "force_converged": False}

    executable, blocked, skipped = _resolve_phase_dependencies(phases)
    _apply_phase_status_updates(task_id, blocked, skipped)

    # v0.24.3: writeback 后必须 reload，否则返回值基于陈旧内存状态计算。
    phases = _load_phases(task_id)

    all_terminal = all(
        p.get("status") in (PHASE_TERMINAL_OK | PHASE_TERMINAL_FAIL)
        for p in phases
    )
    all_failed_or_skipped = all(
        p.get("status") in ("failed", "skipped")
        for p in phases
    )

    # v0.25.1: 多轮 tick 不收敛强失败（CHANGELOG v0.24.4:94 P1）
    engine_iter = _read_engine_iter(task_id)
    force_converged = False
    if not all_terminal:
        engine_iter += 1
        _write_engine_iter(task_id, engine_iter)
        if engine_iter >= PHASE_MAX_ENGINE_ITER:
            # 强收敛：把所有非终态 phase 标 skipped
            new_skipped: set[int] = set()
            for p in phases:
                pid = p.get("phase")
                st = p.get("status", "pending")
                if st in (PHASE_TERMINAL_OK | PHASE_TERMINAL_FAIL):
                    continue
                if pid is not None:
                    new_skipped.add(pid)
            _apply_phase_status_updates(task_id, set(), new_skipped)
            phases = _load_phases(task_id)
            all_terminal = True
            all_failed_or_skipped = all(
                p.get("status") in ("failed", "skipped") for p in phases
            )
            force_converged = True
            # 写 warnings.json + L2 通知
            try:
                warnings_file = ROOT / ".ccc" / "warnings.json"
                existing = []
                if warnings_file.exists():
                    try:
                        existing = json.loads(warnings_file.read_text())
                        if not isinstance(existing, list):
                            existing = []
                    except json.JSONDecodeError:
                        existing = []
                existing.append({
                    "type": "phase_force_converged",
                    "engine_iter": engine_iter,
                    "engine_iter_phase": _current_running_phase(task_id),
                    "task_id": task_id,
                    "detected_at": now_iso(),
                })
                warnings_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
                try:
                    subprocess.run(
                        [
                            "bash",
                            str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                            "L2",
                            f"phases.json: force converged ({task_id})",
                            f"engine_iter={engine_iter} 达到 PHASE_MAX_ENGINE_ITER={PHASE_MAX_ENGINE_ITER}",
                        ],
                        capture_output=True,
                        timeout=5,
                    )
                except Exception:
                    pass
            except OSError:
                pass

    return {
        "executable": sorted(executable),
        "blocked": sorted(blocked),
        "skipped": sorted(skipped),
        "all_terminal": all_terminal,
        "all_failed_or_skipped": all_failed_or_skipped,
        "engine_iter": engine_iter,
        "force_converged": force_converged,
    }


def _read_engine_iter_meta(task_id: str) -> dict:
    """v0.27.1: 读 phases.json metadata 行的完整 engine_iter 元数据。"""
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        return {}
    try:
        for line in phases_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and "engine_iter" in obj:
                    return obj
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return {}


def _write_engine_iter_meta(task_id: str, meta: dict) -> None:
    """v0.27.1: 把 engine_iter 元数据写入 phases.json 顶层 metadata 行。"""
    import fcntl
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        return
    try:
        with open(phases_file, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                lines = f.readlines()
                found = False
                for i, line in enumerate(lines):
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        obj = json.loads(line_s)
                        if isinstance(obj, dict) and "engine_iter" in obj:
                            obj.update(meta)
                            lines[i] = json.dumps(obj, ensure_ascii=False) + chr(10)
                            found = True
                            break
                    except json.JSONDecodeError:
                        continue
                if not found:
                    lines.insert(0, json.dumps(meta, ensure_ascii=False) + chr(10))
                f.seek(0)
                f.truncate()
                f.writelines(lines)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        pass


def _read_engine_iter(task_id: str) -> int:
    """v0.27.1: 读当前 phase 的 engine_iter（phase 切换时自动重置到 0）。"""
    meta = _read_engine_iter_meta(task_id)
    cur_phase = _current_running_phase(task_id)
    if meta.get("engine_iter_phase") != cur_phase:
        return 0
    return meta.get("engine_iter", 0)


def _write_engine_iter(task_id: str, value: int) -> None:
    """v0.27.1: 写 engine_iter + 当前 phase 到 metadata。"""
    cur_phase = _current_running_phase(task_id)
    _write_engine_iter_meta(task_id, {
        "engine_iter": value,
        "engine_iter_phase": cur_phase,
    })
def _move_task_to_abnormal_if_all_terminal_failed(task_id: str) -> bool:
    """v0.24: 如果 task 所有 phase 都 failed/skipped（依赖失败链），移到 abnormal。

    Returns: True if moved, False otherwise.
    """
    phases = _load_phases(task_id)
    if not phases:
        return False
    if not all(p.get("status") in ("failed", "skipped") for p in phases):
        return False
    # 所有 phase 都失败或被跳过 → task 整体异常
    try:
        move_task(task_id, "in_progress", "abnormal")
        # v0.28.0 (R-08): 改用 _log 统一 logger
        _log.error("failure-isolation: %s all phases failed/skipped → abnormal", task_id)
        return True
    except Exception as exc:
        _log.error("failure-isolation: %s move to abnormal failed: %s", task_id, exc)
        return False


_CLAUDE_CLI = "claude"


def _get_relay_url() -> str:
    return os.environ.get("AGENT_PLANNER_BASE_URL", "http://127.0.0.1:4000")


def _get_code_context(ws_path: Path) -> str:
    """动态获取代码上下文：文件树 + 入口文件 + 近期 git 日志

    v0.23 新增：用于注入 product 角色的 plan 生成 prompt。
    设计原则：轻量（<5KB）、聚焦结构概览、不深入实现细节。

    修复 v0.23 对抗性审查问题：
    - A2: 截断确保代码块闭合（不截断代码块内容）
    - A3: 删除冗余 subprocess import（全局已导入）
    - A5: 入口文件过滤增强（排除 vendor/build/tests）
    - A6: 添加简单缓存（模块级字典）
    - A7: 入口文件过滤跳过 symlink（用 is_symlink 检查，3.9 兼容）
    """
    parts = []
    ws = str(ws_path)

    # v0.28.0 (M-002): 模块级缓存 + 300s TTL，过期重算
    cache_key = str(ws_path)
    cached = _get_code_context_cache.get(cache_key)
    if cached is not None:
        result, ts = cached
        if time.monotonic() - ts < _GET_CODE_CONTEXT_TTL_S:
            return result
        # 过期 → 删旧条目，重新计算
        _get_code_context_cache.pop(cache_key, None)

    # A3: 使用全局 subprocess（文件顶部已导入）

    # 1. 代码文件树（Python + TypeScript + 配置）
    try:
        tree = subprocess.run(
            [
                "find",
                ".",
                "(",
                "-name",
                "*.py",
                "-o",
                "-name",
                "*.ts",
                "-o",
                "-name",
                "*.tsx",
                "-o",
                "-name",
                "*.js",
                "-o",
                "-name",
                "*.jsx",
                "-o",
                "-name",
                "*.json",
                "-o",
                "-name",
                "*.yaml",
                "-o",
                "-name",
                "*.yml",
                ")",
                "-not",
                "-path",
                "./node_modules/*",
                "-not",
                "-path",
                "./.venv/*",
                "-not",
                "-path",
                "./__pycache__/*",
                "-not",
                "-path",
                "./.git/*",
                "-not",
                "-path",
                "./.ccc/*",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=ws,
        )
        if tree.returncode == 0:
            lines = tree.stdout.strip().split("\n")
            label = f"{len(lines)} 个源文件"
            if len(lines) > 80:
                label += "，已截断前 80 行"
            shown = lines[:80]
            parts.append(
                f"## 代码文件树（{label}）\n```\n" + "\n".join(shown) + "\n```"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 2. 近期 git 日志
    try:
        git_log = subprocess.run(
            ["git", "log", "--oneline", "-20", "--no-decorate"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=ws,
        )
        if git_log.returncode == 0 and git_log.stdout.strip():
            parts.append("## 近期 git 提交\n```\n" + git_log.stdout.strip() + "\n```")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # A5: 入口文件（最多 2 个，过滤增强 + A7: 用 is_symlink 检查，3.9 兼容）
    exclude_patterns = [
        ".venv",
        "node_modules",
        ".ccc",
        "__pycache__",
        "vendor",
        "build",
        "/tests/",
    ]
    for entry_pattern in [
        "main.py",
        "app.py",
        "server.py",
        "cli.py",
        "index.ts",
        "index.js",
    ]:
        if len([p for p in parts if p.startswith("## 入口文件")]) >= 2:
            break
        # A7 兼容 3.9：rglob 不带 follow_symlinks（Python 3.13+ 才支持），用 is_symlink 过滤
        entries = sorted(
            p for p in ws_path.rglob(entry_pattern) if not p.is_symlink()
        )
        for ef in entries:
            if len([p for p in parts if p.startswith("## 入口文件")]) >= 2:
                break
            try:
                rel = ef.relative_to(ws_path)
                rel_str = str(rel)
                # A5: 增强过滤（排除 tests/ 目录下的入口文件）
                if any(pattern in rel_str for pattern in exclude_patterns):
                    continue
                # 不截断，入口文件内容通常较小
                content = ef.read_text()[:2000]
                parts.append(f"## 入口文件 {rel}\n```\n{content}\n```")
            except (OSError, ValueError):
                continue

    # A6: 写入缓存
    result = "\n\n".join(parts)
    # v0.28.0 (M-002): 加 300s TTL，避免 product_role 多次调用时拿到陈旧快照
    _get_code_context_cache[str(ws_path)] = (result, time.monotonic())
    return result


# v0.28.0 (M-002): 模块级缓存 = {path: (result, ts)} — 300s TTL 过期
_GET_CODE_CONTEXT_TTL_S = 300.0
_get_code_context_cache: dict[str, tuple[str, float]] = {}


def _call_claude_for_plan(task: dict) -> tuple[str, list]:
    """调 claude CLI 生成 plan.md + phases.json（通过中转站 127.0.0.1:4000）"""
    plan_dir = ROOT / ".ccc" / "plans"
    ref_plans = ""
    if plan_dir.exists():
        plan_files = sorted(
            plan_dir.glob("*.plan.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for pf in plan_files[:2]:
            ref_plans += f"--- {pf.name} ---\n{pf.read_text()}\n\n"

    template_plan = (ROOT / "templates" / "plan.plan.md").read_text()
    profile = (ROOT / ".ccc" / "profile.md").read_text()

    code_ctx = _get_code_context(ROOT)

    prompt = (
        f"你是 CCC 产品经理。根据以下信息生成 SPEC-合规的执行 plan。\n\n"
        f"## 项目概况\n{profile[:1500]}\n\n"
        f"## 当前代码状态（v0.23：自动注入）\n{code_ctx[:3000] if code_ctx else '（无代码上下文）'}\n\n"
        f"## 任务\n"
        f"- id: {task['id']}\n"
        f"- title: {task.get('title', '')}\n"
        f"- description: {task.get('description', '')}\n\n"
        f"## Plan 格式（严格按此结构）\n{template_plan}\n\n"
        f"## Phases 格式\n"
        f"每行一个 JSON object：\n"
        f'{{"phase": <int>, "status": "pending", "subtasks": {{"1.1": "pending", ...}}, "timeout": <秒>, "commit": null, "notes": ""}}\n\n'
        f"## 参考历史 plan\n{ref_plans if ref_plans else '（无）'}\n\n"
        f"## 输出要求\n"
        f"输出以下两部分，用分隔符包裹：\n\n"
        f"---PLAN---\n（plan.md 完整内容）\n---END_PLAN---\n"
        f"---PHASES---\n（phases JSONL，每行一个 phase JSON）\n---END_PHASES---\n"
    )

    relay_url = _get_relay_url()
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = relay_url
    try:
        result = subprocess.run(
            [_CLAUDE_CLI, "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited {result.returncode}: {result.stderr[:500]}"
            )

        output = result.stdout

        plan_match = re.search(r"---PLAN---\n(.*?)\n---END_PLAN---", output, re.DOTALL)
        if not plan_match:
            raise RuntimeError("---PLAN--- section not found in Claude output")
        plan_content = plan_match.group(1).strip()

        phases_match = re.search(
            r"---PHASES---\n(.*?)\n---END_PHASES---", output, re.DOTALL
        )
        if not phases_match:
            raise RuntimeError("---PHASES--- section not found in Claude output")

        phases = []
        for line in phases_match.group(1).strip().split("\n"):
            line = line.strip()
            if line:
                phases.append(json.loads(line))

        return plan_content, phases
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI timed out after 300s")


def _generate_fallback_plan(task: dict) -> str:
    """API 不可用时生成 fallback plan"""
    return (
        f"# {task['id']}\n\n"
        f"> 此 plan 由 fallback 自动生成（product API 不可用）\n\n"
        f"## 目标\n"
        f"- {task.get('title', task['id'])}\n"
        f"- {task.get('description', '请手动补充详细描述')}\n\n"
        f"## 文件白名单\n"
        f"- （待补充）\n\n"
        f"## 验收\n"
        f"1. 完成任务目标\n"
        f"2. 相关测试通过\n"
    )


def _generate_fallback_phases() -> list:
    """API 不可用时生成 fallback phases（单 phase）"""
    return [
        {
            "phase": 1,
            "status": "pending",
            "subtasks": {"1.1": "pending"},
            "timeout": 300,
            "commit": None,
            "notes": "fallback",
        }
    ]


def product_role(task_id: str = "") -> dict:
    """产品经理：扫 backlog，或 --promote 调 Claude API 写 SPEC-合规 plan"""
    tasks = list_tasks("backlog")

    if task_id:
        task_id = sanitize_id(task_id)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if not task:
            _log.error("backlog 中未找到 task '%s'", task_id)
            return {
                "role": "product",
                "error": f"task '{task_id}' not found",
                "counts": update_index(),
            }

        _log.info("正在拆解 %s（调 Claude API 生成 plan）...", task_id)
        plan_content = None
        phases = None
        fallback = False
        try:
            plan_content, phases = _call_claude_for_plan(task)
        except RuntimeError as e:
            _log.error("API 调用失败: %s", e)
            _log.info("使用 fallback plan（API 不可用）")
            plan_content = _generate_fallback_plan(task)
            phases = _generate_fallback_phases()
            fallback = True

        plan_dir = ROOT / ".ccc" / "plans"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plan_dir / f"{task_id}.plan.md"
        plan_file.write_text(plan_content)
        _log.info("✓ 写入 %s", plan_file)

        phases_dir = ROOT / ".ccc" / "phases"
        phases_dir.mkdir(parents=True, exist_ok=True)
        phases_file = phases_dir / f"{task_id}.phases.json"
        schema_line = json.dumps({"schema_version": "1.0"}, ensure_ascii=False)
        phases_file.write_text(
            schema_line
            + "\n"
            + "\n".join(json.dumps(p, ensure_ascii=False) for p in phases)
            + "\n"
        )
        _log.info("✓ 写入 %s (%d phases)", phases_file, len(phases))

        move_task(task_id, "backlog", "planned")

        # v0.26 Protocol v1 §5: 自动分配 color_group（首次见 task）
        # 写 phase 列表时给每个 phase 标 color_depth=1（task 自身是父 depth=0）
        try:
            from _board_store import assign_color_group
            color_group = assign_color_group(ROOT, parent_group=task.get("color_group"))
            # 读 task 文件 → 注入 color_group → 写回
            from pathlib import Path as _P
            task_file = _P(".ccc/board/planned") / f"{task_id}.jsonl"
            if task_file.exists():
                task_data = json.loads(task_file.read_text())
                task_data["color_group"] = color_group
                task_data["color_depth"] = 0  # 父任务 depth=0
                task_file.write_text(json.dumps(task_data, ensure_ascii=False) + "\n")
                _log.info("%s assigned color_group=%s depth=0", task_id, color_group)
            # 写 phase color_depth=1（子 phase 继承）
            if phases:
                for p in phases:
                    p.setdefault("color_depth", 1)
                    p.setdefault("color_group", color_group)
                phases_file.write_text(
                    '{"schema_version": "1.1"}'
                    + "\n"
                    + "\n".join(json.dumps(p, ensure_ascii=False) for p in phases)
                    + "\n"
                )
        except Exception as e:
            _log.warning("color assign failed (non-fatal): %s", e)

        result = {
            "role": "product",
            "promoted": task_id,
            "fallback": fallback,
            "counts": update_index(),
        }
        return result

    report = {
        "backlog_count": len(tasks),
        "tasks": [{"id": t["id"], "title": t.get("title", "")} for t in tasks],
        "message": "待办是收件箱。使用 --promote <task_id> 拆解。",
    }
    if tasks:
        _log.info("backlog 有 %d 个待处理:", len(tasks))
        for t in tasks:
            _log.info("  • %s: %s", t["id"], t.get("title", "?"))
        _log.info("提示: 使用 --promote <task_id> 拆解")
    else:
        _log.info("backlog 空")
    return {"role": "product", "report": report, "counts": update_index()}


def dev_role() -> dict:
    """开发工程师: 查 in_progress（重试）→ 查 planned（新的）→ opencode 执行"""
    import subprocess as sp

    moved = []
    task = None
    task_id = ""
    from_col = ""

    # Step 1: 有卡在 in_progress 的任务吗？
    stuck = list_tasks("in_progress")
    if stuck:
        task = stuck[-1]
        task_id = task["id"]
        from_col = "in_progress"
        _log.info("发现卡住任务 %s，准备重试", task_id)

        # 读 phases 里的 retry 计数 + retry_at（JSONL 格式，跳过 schema_version 元数据行）
        phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
        retry = 0
        retry_at = None
        try:
            if phases_file.exists():
                with open(phases_file) as _pf:
                    for _line in _pf:
                        _line = _line.strip()
                        if not _line:
                            continue
                        try:
                            _meta = json.loads(_line)
                            if "schema_version" in _meta:
                                continue  # 跳过 schema_version 元数据行
                        except json.JSONDecodeError:
                            continue
                        parsed = _meta
                        # phases 可能是 JSON 数组 [{...}] 或 JSONL 单行 {...}
                        if isinstance(parsed, list):
                            parsed = parsed[0] if parsed else {}
                        retry = parsed.get("retry", 0)
                        retry_at = parsed.get("retry_at")
                        break
        except json.JSONDecodeError as exc:
            _log.debug("phases parse failed for %s: %s", task_id, exc)

        # ★ 退避前先检查 .done（防退避死锁）
        _done_early = ROOT / ".ccc" / "pids" / f"{task_id}.done"
        if _done_early.exists():
            _log.info("%s .done 存在，跳过退避直接处理结果", task_id)
        else:
            # 退避检查：如果在退避期内，跳过此任务的这一轮
            if retry_at:
                from datetime import datetime as _dt

                try:
                    wait_until = _dt.fromisoformat(retry_at)
                    if _dt.now(timezone.utc) < wait_until.replace(tzinfo=timezone.utc):
                        remaining = (
                            wait_until.replace(tzinfo=timezone.utc)
                            - _dt.now(timezone.utc)
                        ).total_seconds()
                        _log.info(
                            "%s 退避中（还剩 %.0fs），跳过本轮，检查 planned",
                            task_id,
                            remaining,
                        )
                        # 重置 task，使执行流落入 Step 2（planned）
                        task = None
                        task_id = ""
                        from_col = ""
                except (ValueError, TypeError) as exc:
                    _log.debug("retry_at parse failed for %s: %s", task_id, exc)

        # 退避跳过：不增 retry，直接 fall through 到 Step 2（planned）
        if task is not None:
            retry += 1

        if retry >= MAX_RETRY:
            # 达到最大重试 → 异常隔离
            _quarantine(task_id, f"重试{MAX_RETRY}次全部失败，已移入异常列")
            # 同时创建紧急修复任务到 backlog
            bug_id = f"emergency-{task_id}"
            bug_title = (
                f"紧急修复: {task.get('title', task_id)}（重试{MAX_RETRY}次失败）"
            )
            create_task(
                {
                    "id": bug_id,
                    "title": bug_title,
                    "description": f"自动升舱:\n{task_id} 重试{MAX_RETRY}次均失败，已移入异常列。",
                }
            )
            _log.error(
                "%s 重试%d次失败 → quarantine + 升舱 %s",
                task_id,
                MAX_RETRY,
                bug_id,
            )
            return {
                "role": "dev",
                "moved": [],
                "error": "quarantined",
                "counts": update_index(),
            }

        # 计算退避时间（v0.24.7 A24-14: retry=0 也强制 60s 最小退避 first backoff）
        backoff = _backoff_seconds(retry - 1) if retry else 60
        retry_at_iso = (
            (datetime.now(timezone.utc) + timedelta(seconds=backoff)).isoformat()
            if retry >= 0
            else None
        )
        # 更新 retry 计数 + retry_at（JSONL，跳过 schema_version 元数据行）
        try:
            if phases_file.exists():
                lines = phases_file.read_text().split("\n")
                for i, _line in enumerate(lines):
                    _line_s = _line.strip()
                    if not _line_s:
                        continue
                    try:
                        _meta = json.loads(_line_s)
                        if "schema_version" in _meta:
                            continue  # 跳过 schema_version 元数据行
                    except json.JSONDecodeError:
                        continue
                    phase = _meta
                    # phases 可能是 JSON 数组 [{...}] 或 JSONL 单行 {...}
                    if isinstance(phase, list):
                        phase = phase[0] if phase else {}
                    phase["retry"] = retry
                    phase["retry_at"] = retry_at_iso
                    lines[i] = json.dumps(phase, ensure_ascii=False)
                    break
                phases_file.write_text("\n".join(lines))
        except json.JSONDecodeError as exc:
            _log.debug("phases update failed for %s: %s", task_id, exc)
        _log.info("%s 第 %d/%d 次重试，退避 %s", task_id, retry, MAX_RETRY, backoff)

    # Step 2: in_progress 无事，取 planned（迭代，跳过错/缺 plan 的任务）
    if not task:
        planned = list_tasks("planned")
        if not planned:
            return {
                "role": "dev",
                "moved": [],
                "counts": update_index(),
                "info": "无任务",
            }
        # 迭代 planned 任务，跳过缺 plan/phases 的（移入异常），处理第一个合法的
        for candidate in planned:
            cid = candidate["id"]
            cplan = ROOT / ".ccc" / "plans" / f"{cid}.plan.md"
            cphases = ROOT / ".ccc" / "phases" / f"{cid}.phases.json"
            if cplan.exists() and cphases.exists():
                task = candidate
                task_id = cid
                from_col = "planned"
                break
            else:
                # 缺失 plan/phases → 移入异常列，不阻塞其他任务
                _quarantine(cid, "dev_role: 缺 plan 或 phases 文件, 无法执行")
                _log.info("%s 缺 plan/phases, 已移入 abnormal", cid)
        if not task:
            return {
                "role": "dev",
                "moved": [],
                "counts": update_index(),
                "info": "planned 任务均缺 plan/phases",
            }
        move_task(task_id, "planned", "in_progress")

    plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"

    # 从 phases.json 读 timeout
    timeout_s = _load_timeout(phases_file, default=cfg.default_timeout)
    phase_id = f"{task_id}-p1"

    # 从 plan.md 生成 executor prompt
    plan_content = plan.read_text()
    prompt = (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## Plan\n\n{plan_content}\n\n"
        f"## 完成定义\n"
        f"1. 实现所有需求\n"
        f"2. 跑对应的测试（如有）\n"
        f"3. 提交一个 commit（message 以 {task_id} 开头）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 plan 文件白名单\n"
    )

    # 写 prompt 文件到 .ccc/pids/（跟其他 task 文件一起清理，不泄漏）
    pids_dir = ROOT / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)

    try:
        _log.info(
            "%s phase=%s timeout=%s retry=%d", task_id, phase_id, timeout_s, retry if from_col == "in_progress" else 0)
        done_path = ROOT / ".ccc" / "pids" / f"{task_id}.done"
        exitcode_path = ROOT / ".ccc" / "pids" / f"{task_id}.exitcode"
        result_path = ROOT / ".ccc" / "reports" / f"{task_id}.result.json"
        pid_path = ROOT / ".ccc" / "pids" / f"{task_id}.pid"

        # ❗.done 检查必须在 PID 检查之前
        # stale PID 被回收后 os.kill 返回成功，先查 .done 再查 PID
        if done_path.exists():
            exit_code = (
                exitcode_path.read_text().strip() if exitcode_path.exists() else "?"
            )
            result_raw = result_path.read_text() if result_path.exists() else "{}"
            report_dir = ROOT / ".ccc" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_dir.joinpath(f"{task_id}.report.md").write_text(
                f"# {task_id} 执行报告\n\n## 信息\n- Phase: {phase_id}\n"
                f"- 退出码: {exit_code}\n\n## 输出\n```\n{result_raw[:2000]}\n```\n"
            )
            for p in [
                done_path,
                exitcode_path,
                pid_path,
                result_path,
                ROOT / ".ccc" / "pids" / f"{task_id}.prompt.md",
            ]:
                try:
                    p.unlink()
                except OSError as exc:
                    _log.debug("pids cleanup %s: %s", p, exc)
            if exit_code == "0":
                move_task(task_id, "in_progress", "testing")
                moved.append(task_id)
                _log.info("%s ✓ → testing", task_id)
            else:
                _log.error(
                    "%s ✗ rc=%s（留在 in_progress 下轮重试）", task_id, exit_code
                )
            return {"role": "dev", "moved": moved, "counts": update_index()}

        # PID 检查：.done 不存在时确认 opencode 是否还在跑
        if pid_path.exists():
            try:
                old_pid = int(pid_path.read_text().strip())
                try:
                    os.kill(old_pid, 0)
                    _log.info("%s opencode %d 仍在运行，跳过", task_id, old_pid)
                    return {
                        "role": "dev",
                        "moved": [],
                        "counts": update_index(),
                        "info": f"opencode PID={old_pid} 运行中",
                    }
                except OSError:
                    # stale PID
                    _log.info("%s PID %d 不存在，清理后重试", task_id, old_pid)
                    try:
                        pid_path.unlink()
                    except OSError as exc:
                        _log.debug("stale pid unlink failed for %s: %s", task_id, exc)
            except (ValueError, OSError) as exc:
                _log.debug("pid check parse failed for %s: %s", task_id, exc)

        # 启动 opencode（通过 runner.sh 持久化结果）
        report_dir = ROOT / ".ccc" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{task_id}.report.md"

        proc = sp.Popen(
            [
                str(CCC_HOME / "scripts" / "opencode-runner.sh"),
                task_id,
                str(CCC_HOME),
                str(ROOT),
                "--phase",
                phase_id,
                "--prompt",
                prompt_file,
                "--timeout",
                str(timeout_s),
            ],
            start_new_session=True,
        )
        pid_dir = ROOT / ".ccc" / "pids"
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
        report_path.write_text(
            f"# {task_id} 执行报告\n\n## 信息\n- 状态: 运行中\n- PID: {proc.pid}\n- Started: {now_iso()}\n"
        )
        _log.info("%s 后台启动 PID=%d，下轮检查结果", task_id, proc.pid)

    except Exception as e:  # debug
        import traceback as _tb
        _log.error("\n%s 启动失败: %s\n%s", task_id, e, _tb.format_exc())
    finally:
        # prompt 保留给后台读
        pass

    return {"role": "dev", "moved": moved, "counts": update_index()}


def _is_path_in_root(p: Path) -> bool:
    """检查解析后的路径是否在 ROOT 范围内，防止路径穿越 (CWE-22)"""
    try:
        resolved = p.resolve()
        root_resolved = ROOT.resolve()
        return root_resolved in resolved.parents or resolved == root_resolved
    except (OSError, RuntimeError):
        return False


def _parse_plan_scope(task_id: str) -> list[str]:
    """从 plan.md 读文件白名单

    兼容两种格式：
       新模板：## 范围 → - **只改文件**： → 后续 - file 行
       旧格式：## 文件白名单 → 直接 - file 行

    安全：返回的路径均已校验在 ROOT 范围内，防止路径穿越 (CWE-22/94)。
    """
    plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    if not plan.exists():
        return []
    content = plan.read_text()

    def _clean(f: str) -> str:
        """提取纯文件路径（去掉尾部注释/说明）"""
        f = f.strip().strip("`\"'*")
        # 去掉尾部中文/括号说明（product_role 增强 → 空）
        m = re.match(r"^([\w./~@+\-\[\]]+)", f)
        if m:
            f = m.group(1)
        # 如果还多出来尾缀（如括号前有空格）
        for sep in ("（", "(", "`（", "`("):
            idx = f.find(sep)
            if idx > 0:
                f = f[:idx]
        return f.strip().rstrip(".")

    in_scope = False
    collecting_only = False
    old_format = False
    files = []
    for line in content.split("\n"):
        if line.startswith("## 范围"):
            in_scope = True
            old_format = False
            continue
        if line.startswith("## 文件白名单") or line.startswith("## 文件"):
            in_scope = True
            old_format = True
            continue
        if in_scope and line.startswith("## "):
            break
        if not in_scope:
            continue
        stripped = line.strip()

        if not old_format:
            # 新模板格式
            if "**只改文件" in stripped and (
                stripped.startswith("- ") or stripped.startswith("* ")
            ):
                collecting_only = True
                after_label = stripped.split("**")[-1].lstrip("：:").strip()
                if after_label:
                    for f in after_label.split():
                        f_clean = _clean(f)
                        if f_clean:
                            files.append(f_clean)
                continue
            if "**不改文件" in stripped and (
                stripped.startswith("- ") or stripped.startswith("* ")
            ):
                break
            if collecting_only:
                if stripped.startswith("- ") or stripped.startswith("* "):
                    f = _clean(stripped[2:])
                    if (
                        f
                        and not f.startswith("(")
                        and not f.startswith("不")
                        and f not in ("只改文件", "不改文件")
                    ):
                        files.append(f)
        else:
            # 旧格式：直接收集 - 条目
            if stripped.startswith("- ") or stripped.startswith("* "):
                f = _clean(stripped[2:])
                if f and not f.startswith("不"):
                    files.append(f)
    # 安全校验：过滤掉穿越 ROOT 的路径 (CWE-22)
    validated = []
    for f in files:
        candidate = ROOT / f
        if _is_path_in_root(candidate):
            validated.append(f)
    return validated


def _get_git_diff(workspace: Path, since: str = "HEAD~1", task_id: str = "") -> tuple[str, str]:
    """取 git diff 改动，返回 (stat, full_diff)。

    若 task_id 提供，优先按 task 关联 commit 取 diff（G1 修复：reviewer 只审单个 task 的改动）。
    否则按 since ref。

    Args:
        workspace: 项目根目录
        since: git diff 的 ref（默认 HEAD~1 = 最近一次 commit，task_id 提供时忽略）
        task_id: 任务 ID，用于过滤 git log --grep

    Returns:
        (stat_output, diff_output)，git 不可用时都为空字符串
    """
    import subprocess as sp

    try:
        # G1: 优先按 task_id 找关联 commit
        # v0.24.6 (A24-08): 优先 phases.json 里记录的 commit（防 task_id grep 复用导致
        # 拿到历史 commit 的 diff，而非当前本次的 diff）；phases.json 缺失再 fallback 到 grep
        commit = ""
        if task_id:
            phases_file = workspace / ".ccc" / "phases" / f"{task_id}.phases.json"
            if phases_file.exists():
                for line in phases_file.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        phase = json.loads(line)
                        if phase.get("commit"):
                            commit = phase["commit"]
                            break
                    except json.JSONDecodeError:
                        continue
            # fallback: git log --grep task_id（仅在 phases.json 无记录时用）
            if not commit:
                log_r = sp.run(
                    ["git", "log", "--all", "--oneline", "--grep", task_id, "--format=%H", "--max-count=1"],
                    cwd=workspace, capture_output=True, text=True, timeout=10,
                )
                commit = log_r.stdout.strip() if log_r.returncode == 0 else ""

        if commit:
            # task 级别的 diff
            stat_r = sp.run(
                ["git", "diff", f"{commit}^..{commit}", "--stat"],
                cwd=workspace, capture_output=True, text=True, timeout=10,
            )
            diff_r = sp.run(
                ["git", "diff", f"{commit}^..{commit}"],
                cwd=workspace, capture_output=True, text=True, timeout=30,
            )
            # 若父 commit 不存在（首次 commit），用 --root
            if stat_r.returncode != 0:
                stat_r = sp.run(
                    ["git", "diff", "--root", commit, "--stat"],
                    cwd=workspace, capture_output=True, text=True, timeout=10,
                )
                diff_r = sp.run(
                    ["git", "diff", "--root", commit],
                    cwd=workspace, capture_output=True, text=True, timeout=30,
                )
            return stat_r.stdout or "", diff_r.stdout or ""

        # 无 task_id / 没找到 commit：按 since 走（原逻辑 + HEAD~1 不存在降级）
        rev_r = sp.run(
            ["git", "rev-parse", "--verify", since],
            cwd=workspace, capture_output=True, timeout=5,
        )
        ref = since if rev_r.returncode == 0 else "--root"

        stat_r = sp.run(
            ["git", "diff", ref, "--stat"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        diff_r = sp.run(
            ["git", "diff", ref],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # v0.28.0 (M-008): diff 为空时显式 warning（无 commit 或初次启动场景）
        if not stat_r.stdout and not diff_r.stdout:
            _log.warning(
                "git diff 为空 (ref=%s) — 仓库可能无 commit 或 since 指向了初始", ref
            )
        return stat_r.stdout or "", diff_r.stdout or ""
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.error("[reviewer] git diff 失败: %s", exc)
        return "", ""


def _review_with_llm(
    task_id: str, diff_stat: str, full_diff: str, plan_text: str,
    size_class: str = "medium",
) -> dict:
    """调 Claude API 审查代码。返回 {"verdict": "pass"|"fail", "findings": [...], "summary": "..."}。

    fallback: API 不可用或解析失败 → 返回 {"verdict": "fallback", "reason": "..."}

    v0.24.1: size_class="large" 时追加 impact 分析指令（影响面/风险等级）。
    """
    import os
    import re as _re
    import subprocess as _sp

    if not full_diff and not diff_stat:
        return {"verdict": "fallback", "reason": "no git diff"}

    impact_section = ""
    if size_class == "large":
        impact_section = (
            "## 重点检查（large 类变更，>50 行）\n"
            "6. **影响面分析**：列出本次改动触及的模块 + 上下游调用方 + 是否可能影响其他 task\n"
            "7. **风险等级**：评估本次改动风险（high/medium/low）并说明理由\n"
            "8. **回归路径**：列出需要复测的关键功能点（必须包含 plan 验收清单之外的隐性影响）\n\n"
        )

    prompt = (
        "你是 CCC 资深代码审查员。审查下面这次代码改动，按 plan 验收清单逐条核对。\n\n"
        "## Plan 验收清单\n"
        f"{plan_text[:3000]}\n\n"
        "## 改动概览 (git diff --stat)\n"
        f"```\n{diff_stat[:2000]}\n```\n\n"
        "## 改动详情 (git diff)\n"
        f"```\n{full_diff[:8000]}\n```\n\n"
        "## 审查清单（逐条核对）\n"
        "1. 数据流正确性（输入/输出/边界）\n"
        "2. 错误处理（异常/边界/资源泄漏）\n"
        "3. 安全（SQL 注入/路径遍历/凭据泄漏/危险函数）\n"
        "4. 命名与可读性\n"
        "5. 是否与 plan 验收清单一致\n\n"
        f"{impact_section}"
        "## 输出要求\n"
        "只输出以下 JSON，不要包装 markdown 代码块，不要附加任何解释：\n"
        '{"verdict": "pass" 或 "fail", '
        '"findings": [{"severity": "high"|"medium"|"low", "file": "...", "line": N, '
        '"issue": "...", "suggestion": "..."}], '
        '"summary": "一句话总评"}\n'
    )

    relay = os.environ.get("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = relay
    env["CLAUDE_CODE_NONINTERACTIVE"] = "1"  # 禁止任何交互询问
    try:
        # prompt 可能很大（>1MB），写临时文件并 shell 重定向，避免 subprocess.PIPE buffer 截断
        # v0.24.7 (A24-24): 写到 ~/.ccc/prompts/ 私有目录 + mode 0o600，
        # 防 /tmp 下被同用户其他进程读取（review prompt 可能含 plan 描述）
        import tempfile as _tempfile
        _review_prompt_dir = Path.home() / ".ccc" / "prompts"
        _review_prompt_dir.mkdir(parents=True, exist_ok=True)
        _prompt_fd, _prompt_file = _tempfile.mkstemp(
            suffix=".md", prefix="review-prompt-", dir=str(_review_prompt_dir)
        )
        try:
            os.write(_prompt_fd, prompt.encode("utf-8"))
            os.chmod(_prompt_file, 0o600)
        finally:
            os.close(_prompt_fd)
        try:
            with open(_prompt_file, "rb") as f:
                data = f.read()
            r = _sp.run(
                [_CLAUDE_CLI, "-p", "--model", "flash"],
                input=data,
                capture_output=True,
                text=False,  # bytes 注入必须 text=False，否则 'bytes' has no 'encode'
                timeout=300,
                env=env,
            )
        finally:
            try:
                os.unlink(_prompt_file)
            except OSError:
                pass
        if r.returncode != 0:
            stderr = r.stderr.decode("utf-8", errors="replace") if isinstance(r.stderr, bytes) else r.stderr
            return {
                "verdict": "fallback",
                "reason": f"claude rc={r.returncode}: {stderr[:200]}",
            }
        output = r.stdout.decode("utf-8", errors="replace") if isinstance(r.stdout, bytes) else r.stdout
        # 尝试从输出抓 JSON：优先 markdown 代码块，其次裸 JSON
        m = _re.search(r"```(?:json)?\s*\n?(\{[\s\S]*?\"verdict\"[\s\S]*?\})\s*\n?```", output)
        if not m:
            m = _re.search(r"\{[\s\S]*?\"verdict\"[\s\S]*?\}", output)
        if not m:
            return {"verdict": "fallback", "reason": "no JSON in Claude output"}
        try:
            # 优先用捕获组（第一正则 capture group 1 = 干净 JSON），否则用全匹配
            json_str = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
            # Claude 输出里可能有控制字符或转义错误，先尝试宽松解析：
            # 1. 直接 parse
            # 2. 替换常见控制字符再试
            data = None
            for candidate in (json_str, _re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', json_str)):
                try:
                    data = json.loads(candidate)
                    break
                except json.JSONDecodeError:
                    continue
            if data is None:
                raise json.JSONDecodeError("all candidates failed", json_str, 0)
            if data.get("verdict") in ("pass", "fail"):
                return data
            return {
                "verdict": "fallback",
                "reason": f"unexpected verdict: {data.get('verdict')}",
            }
        except json.JSONDecodeError as exc:
            return {"verdict": "fallback", "reason": f"JSON parse failed: {exc}"}
    except _sp.TimeoutExpired:
        return {"verdict": "fallback", "reason": "claude timeout (300s)"}


def _py_compile_fallback(task_id: str, files: list[str]) -> bool:
    """reviewer LLM 失败时的 fallback：py_compile 静态语法检查。"""
    import subprocess as sp

    for f in files:
        if not f.endswith(".py") or not Path(f).exists():
            continue
        r = sp.run(
            ["python3", "-m", "py_compile", str(f)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            _log.error(
                "[reviewer-fallback] %s py_compile %s FAIL: %s",
                task_id,
                Path(f).name,
                r.stderr[:200],
            )
            return False
    return True


# v0.24.1: reviewer 按变更量分级阈值
REVIEW_SIZE_SMALL_MAX = 10   # ≤10 行 → small（跳过 LLM）
REVIEW_SIZE_MEDIUM_MAX = 50  # 11-50 行 → medium（标准 LLM）
                              # >50 行 → large（LLM + impact 分析）


def _parse_diff_size(stat_output: str) -> int | None:
    """解析 git diff --stat 输出，统计总变更行数（insertions + deletions）。

    stat 行格式如: "scripts/ccc-board.py | 42 +++++++++++++--------"
    最后一行格式: "3 files changed, 120 insertions(+), 45 deletions(-)"

    v0.24.3: 返回 None 表示无法解析（缺 summary 行 / diff 为空），
    调用方应 fail-fast 而不是把缺失当成 0 行变更静默通过。
    """
    import re

    insertions = 0
    deletions = 0
    found_summary = False
    for line in stat_output.splitlines():
        line = line.strip()
        if not line:
            continue
        # summary 行优先：无 `|` 但含 insertion/deletion
        if "insertion" in line or "deletion" in line:
            ins_m = re.search(r"(\d+)\s+insertion", line)
            del_m = re.search(r"(\d+)\s+deletion", line)
            if ins_m:
                insertions += int(ins_m.group(1))
                found_summary = True
            if del_m:
                deletions += int(del_m.group(1))
                found_summary = True
            continue
        # file 行（带 `|`）：跳过 —— 计数靠 summary 行
        if "|" not in line:
            continue
    if not found_summary:
        return None
    return insertions + deletions


def _classify_review_size(stat_output: str) -> tuple[str, int | None]:
    """v0.24.1: 按变更量分级。

    Returns:
        ("small" | "medium" | "large", total_changed_lines)
        total=None 表示无法解析（diff 缺 summary 行），调用方应 fail-fast
    """
    total = _parse_diff_size(stat_output)
    if total is None:
        return ("unknown", None)
    if total <= REVIEW_SIZE_SMALL_MAX:
        return ("small", total)
    if total <= REVIEW_SIZE_MEDIUM_MAX:
        return ("medium", total)
    return ("large", total)


def reviewer_role() -> dict:
    """代码审查员: 扫 testing → LLM 审查 git diff + plan 验收清单 → 通过则挪 verified

    v0.24.1: 按变更量分级
      - small (≤10 行): 跳过 LLM，仅 py_compile 静态检查
      - medium (10-50 行): 标准 LLM 审查
      - large (>50 行): LLM + impact 分析（影响面/风险等级）

    v0.24.5: 加 per-task advisory lock（A24-01 防并发 reviewer 实例写同 task 的 review.md）
    v0.24.5: medium/large fallback 路径强制 quarantine（A24-03/A24-04 防 v0.23 G2 bypass 复发）
    """
    moved = []
    lock_dir = ROOT / ".ccc" / "review-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    for task in list_tasks("testing"):
        task_id = task["id"]
        # v0.24.5 (A24-01): per-task advisory lock 防并发 reviewer 写 review.md
        # macOS 不支持 O_WRLOCK，用 O_EXCL 创建 + 0o600 模拟 advisory lock
        lock_path = lock_dir / f"{task_id}.lock"
        try:
            _lock_fd = os.open(
                str(lock_path),
                os.O_CREAT | os.O_EXCL | os.O_RDWR,
                0o600,
            )
        except FileExistsError:
            # 另一个 reviewer 实例正在审本 task → 跳过本轮，避免文件竞态覆盖
            _log.error("[reviewer] %s ⏸ 持锁中，跳过本轮", task_id)
            continue
        try:
            result = _review_one_task(task_id)
            if result:
                moved.append(task_id)
        finally:
            try:
                os.close(_lock_fd)
                os.unlink(lock_path)
            except OSError:
                pass
    return {"role": "reviewer", "moved": moved, "counts": update_index()}


def _review_one_task(task_id: str) -> bool:
    """单个 task 的 reviewer 处理（v0.24.5 抽取，便于 advisory lock 包住）。返回是否移 verified。

    v0.24.5 (A24-03/A24-04): medium/large 类 LLM fallback 一律 quarantine + L2 告警，
    禁止仅凭 py_compile 或 plan 验收清单静默 verified（v0.23 G2 bypass 复发红线）。
    small 类仍走原 py_compile / plan-only 路径。
    """
    task = next((t for t in list_tasks("testing") if t["id"] == task_id), None)
    if task is None:
        return False
    plan_file = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    plan_text = plan_file.read_text() if plan_file.exists() else ""

    # 1. 取 git diff（G1: 按 task_id 过滤，只审本 task 的改动）
    diff_stat, full_diff = _get_git_diff(ROOT, task_id=task_id)

    # v0.24.1: 按变更量分级，决定是否需要 LLM
    size_class, total_lines = _classify_review_size(diff_stat)
    # v0.24.3: diff 无法解析（缺 summary 行）→ quarantine，不能静默放行
    if size_class == "unknown":
        _quarantine(task_id, reason="v0.24.3 reviewer: diff stat 缺 summary 行，无法分级")
        _log.error(
            "[reviewer] %s ✗ diff stat 解析失败（缺 summary），quarantine",
            task_id,
        )
        return False
    _log.info("[reviewer] %s size=%s lines=%s", task_id, size_class, total_lines)

    # 写审查报告（共用目录）
    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    review_md = report_dir / f"{task_id}.review.md"

    # small 类：跳过 LLM，走 py_compile 静态检查（保留原逻辑）
    if size_class == "small":
        files = _parse_plan_scope(task_id)
        if not files:
            files = [str(p) for p in (ROOT / "scripts").rglob("*.py")]
        import glob as _glob
        py_files = []
        for f in files:
            matched = _glob.glob(str(ROOT / f)) if "*" in f else [str(ROOT / f)]
            matched = [m for m in matched if _is_path_in_root(Path(m))]
            py_files.extend(matched)
        py_files = [f for f in py_files if f.endswith(".py") and Path(f).exists()]

        if py_files and _py_compile_fallback(task_id, py_files):
            move_task(task_id, "testing", "verified")
            review_md.write_text(
                f"# {task_id} Review\n\n"
                f"## Verdict: **PASS**\n\n"
                f"## Size Class: **small** ({total_lines} 行)\n\n"
                f"v0.24.1: small 类变更跳过 LLM，仅 py_compile 静态检查通过。\n\n"
                f"## Files Checked ({len(py_files)} 条)\n\n"
                + "\n".join(f"- {Path(f).name}" for f in py_files)
            )
            _log.info("[reviewer] %s ✓ small-class static pass (%s 行)", task_id, total_lines)
            return True
        elif not py_files:
            if not full_diff.strip():
                _quarantine(task_id, reason="v0.24.3 small-class: 无 py 文件 + diff 为空")
                _log.error(
                    "[reviewer] %s ✗ small-class quarantine: 空 diff",
                    task_id,
                )
                return False
            if "## 验收" in plan_text or "## 验证" in plan_text:
                move_task(task_id, "testing", "verified")
                review_md.write_text(
                    f"# {task_id} Review\n\n"
                    f"## Verdict: **PASS**\n\n"
                    f"## Size Class: **small** ({total_lines} 行)\n\n"
                    f"v0.24.1: small 类变更无 py 文件，信任 plan 验收清单（diff 非空已校验）。\n"
                )
                _log.info("[reviewer] %s ✓ small-class plan-only pass", task_id)
                return True
            _quarantine(task_id, reason="v0.24.1 small-class: 无 py 文件 + 无验收清单")
            _log.error("[reviewer] %s ✗ small-class quarantine: 无静态可检查项", task_id)
            return False
        else:
            _log.error(
                "[reviewer] %s ✗ small-class py_compile 失败，留在 testing",
                task_id,
            )
            return False

    # medium / large：走 LLM，large 加 impact 分析提示
    verdict_data = _review_with_llm(task_id, diff_stat, full_diff, plan_text, size_class=size_class)
    verdict = verdict_data.get("verdict", "fallback")
    summary = verdict_data.get("summary", "")

    review_md.write_text(
        f"# {task_id} Review\n\n"
        f"## Verdict: **{verdict.upper()}**\n\n"
        f"## Size Class: **{size_class}** ({total_lines} 行)\n\n"
        f"{summary}\n\n"
        f"## Findings ({len(verdict_data.get('findings', []))} 条)\n\n"
        f"```json\n{json.dumps(verdict_data, ensure_ascii=False, indent=2)}\n```\n"
    )

    if verdict == "pass":
        move_task(task_id, "testing", "verified")
        _log.info("[reviewer] %s ✓ LLM pass", task_id)
        return True
    if verdict == "fail":
        _log.error(
            "[reviewer] %s ✗ LLM fail（%d issues），留在 testing",
            task_id,
            len(verdict_data.get("findings", [])),
        )
        return False

    # v0.24.5 (A24-03/A24-04): medium/large fallback 一律 quarantine + L2 告警
    # 禁止仅凭 py_compile 或 plan 验收清单静默 verified（v0.23 G2 bypass 复发红线）
    reason = (
        f"v0.24.5 fallback quarantine: {size_class}-class LLM 不可用，"
        f"reason={verdict_data.get('reason', 'unknown')}；"
        f"放弃静默 verified，强制人工介入"
    )
    _quarantine(task_id, reason=reason)
    _log.error(
        "[reviewer] %s ✗ %s-class fallback quarantine: %s",
        task_id,
        size_class,
        verdict_data.get("reason", "unknown"),
    )
    # L2 桌面通知：fallback bypass 复发是 high-severity，必须人工看见
    try:
        subprocess.run(
            [
                "bash",
                str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                "L2",
                f"reviewer fallback quarantine: {task_id} ({size_class})",
                reason[:200],
            ],
            capture_output=True,
            timeout=10,
        )
    except Exception as e:
        _log.error("[reviewer] notify failed: %s", e)
    return False


def tester_role() -> dict:
    """测试工程师: 扫 testing → 按 plan 跑验证 → 通过则挪 verified"""
    import subprocess as sp

    moved = []
    for task in list_tasks("testing"):
        task_id = task["id"]
        plan_file = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
        verify_commands = []
        if plan_file.exists():
            content = plan_file.read_text()
            in_verify = False
            for line in content.split("\n"):
                if line.startswith("## 验收") or line.startswith("## 验证"):
                    in_verify = True
                    continue
                if in_verify and line.startswith("## "):
                    break
                if (
                    in_verify
                    and line.strip().startswith("- ")
                    and not line.strip().startswith("- 不")
                ):
                    cmd = line.strip()[2:].strip()
                    verify_commands.append(cmd)

        # fallback: 如果没有验收项，跑 pytest
        if not verify_commands:
            verify_commands = [
                f"python3 -m pytest {ROOT / 'tests' / 'scripts'} -q --tb=line --timeout=60"
            ]

        # 强制 baseline（v0.21.3）：项目有 tests/ 时追加 pytest + 覆盖率门槛
        has_pyproject = (ROOT / "pyproject.toml").exists()
        if has_pyproject and not any("pytest" in c for c in verify_commands):
            verify_commands.append(
                f"python3 -m pytest tests/ -q --tb=line --timeout=60 --cov=src --cov-fail-under=80"
            )

        all_ok = True
        for cmd in verify_commands:
            if not all_ok:
                break
            r = sp.run(
                shlex.split(cmd),
                shell=False,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=ROOT,
            )
            if r.returncode != 0:
                all_ok = False
                _log.error(
                    "[tester] %s FAIL: %s... → %s",
                    task_id,
                    cmd[:80],
                    r.stdout[-300:],
                )

        if all_ok:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
            _log.info("[tester] %s ✓（验证 {len(verify_commands)} 项）", task_id)
    return {"role": "tester", "moved": moved, "counts": update_index()}


def ops_role() -> dict:
    """运维监控: 健康检查 + stale 检测 + 孤儿 PID 清理 + 告警"""
    health = {
        "opencode_pids": len(
            list((Path.home() / ".ccc" / "opencode-pids").glob("*.pid"))
        ),
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob("*-L*.md"))),
        "git_ahead": 0,
        "stale_detected": 0,
        "orphan_pids_cleaned": 0,
    }

    # 1. Stale 检测：in_progress 超时 → 异常列
    from datetime import datetime as _dt

    now = _dt.now(timezone.utc)
    for task in list_tasks("in_progress"):
        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            hours_stale = (now - updated).total_seconds() / 3600
            if hours_stale > MAX_STALE_HOURS:
                _quarantine(
                    task["id"],
                    f"in_progress 滞留 {hours_stale:.1f}h（阈值 {MAX_STALE_HOURS}h），自动隔离",
                )
                health["stale_detected"] += 1
                _log.info("[ops] stale: {task['id']} in_progress 滞留 {hours_stale:.1f}h → abnormal")
        except (ValueError, TypeError):
            pass

    # 2. 孤儿 PID 清理
    pid_dir = ROOT / ".ccc" / "pids"
    if pid_dir.exists():
        for f in pid_dir.glob("*.pid"):
            try:
                pid = int(f.read_text().strip())
                os.kill(pid, 0)  # 检查进程是否存在
            except (ValueError, OSError, ProcessLookupError):
                stem = f.stem
                f.unlink()
                for suffix in [".done", ".exitcode", ".report.md", ".result.json"]:
                    extra = pid_dir.parent / "reports" / f"{stem}{suffix}"
                    if extra.exists():
                        extra.unlink(missing_ok=True)
                health["orphan_pids_cleaned"] += 1
                _log.info("[ops] 清理孤儿 PID: %s", stem)

    # 3. 检查 abnormal 列任务（上报）
    abnormal_tasks = list_tasks("abnormal")
    if abnormal_tasks:
        _log.info("[ops] ⚠ abnormal 列有 {len(abnormal_tasks)} 个任务需处理:")
        for t in abnormal_tasks:
            _log.info("  • {t['id']}: {t.get('note', '?')[:120]}")
        health["abnormal_count"] = len(abnormal_tasks)

    # 4. git ahead check
    import subprocess as sp

    for proj in [
        ROOT,
        ROOT.parent / "qx-observer",
        ROOT.parent / "xianyu",
        ROOT.parent / "projects" / "qx",
    ]:
        if (proj / ".git").exists():
            r = sp.run(
                ["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"],
                capture_output=True,
                text=True,
                cwd=proj,
                timeout=10,
            )
            if r.returncode == 0:
                ahead = r.stdout.strip().split()[-1] if r.stdout.strip() else "0"
                health[f"ahead_{proj.name}"] = int(ahead)

    # 5. launchd 自检：检查 7 角色 plist 是否存活
    roles_check = ["product", "dev", "reviewer", "tester", "ops", "kb", "regress"]
    launchd_up = []
    for role in roles_check:
        r = sp.run(
            ["launchctl", "list", f"com.ccc.{role}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and "PID" in r.stdout:
            launchd_up.append(role)
        else:
            _log.info("[ops] ⚠ com.ccc.%s 未运行", role)
    health["launchd_up"] = launchd_up
    health["launchd_missing"] = [r for r in roles_check if r not in launchd_up]

    # 4.5 日志清理：删除 >30 天的 role 日志
    if (Path.home() / ".ccc" / "logs").exists():
        _now_ts = time.time()
        _cutoff = _now_ts - 30 * 86400
        for _lf in (Path.home() / ".ccc" / "logs").glob("role-*.log"):
            if _lf.stat().st_mtime < _cutoff:
                _lf.unlink(missing_ok=True)

    # 6. 指标收集 → .ccc/metrics.json
    pid_dir = ROOT / ".ccc" / "pids"
    metrics = {
        "updated_at": now_iso(),
        "tasks_in_flight": len(list_tasks("in_progress")) + len(list_tasks("testing")),
        "abnormal_count": len(list_tasks("abnormal")),
        "pids_count": len(list(pid_dir.glob("*.pid"))) if pid_dir.exists() else 0,
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob("*-L*.md"))),
        "launchd_missing": health["launchd_missing"],
    }
    metrics_file = ROOT / ".ccc" / "metrics.json"
    metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")

    return {"role": "ops", "health": health}


def _extract_agents_suggestions(
    filepath: Path, task_id: str, source: str
) -> list[dict]:
    """从 report/verdict 文件中提取 AGENTS.md 建议"""
    import re

    suggestions = []
    if not filepath.exists():
        return suggestions
    content = filepath.read_text()
    # tempered dot: match content until blank line, ---, next marker, or end
    pattern = re.compile(
        r"> \*\*AGENTS\.md 建议:\*\*\s*((?:(?!> \*\*AGENTS\.md 建议:|\n\n|\n---).)*)",
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        text = match.group(1).strip()
        text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
        text = text.strip()
        if text:
            suggestions.append({"task_id": task_id, "source": source, "content": text})
    return suggestions


def kb_role() -> dict:
    """知识管理员: 扫 verified → 归档 + git tag → 挪 released → 收集 AGENTS.md 建议"""
    import subprocess as sp

    moved = []
    all_suggestions: list[dict] = []
    for task in list_tasks("verified"):
        task_id = task["id"]
        # 从 VERSION 读版本号（缺失则 fallback 到 0.0.0）
        version_file = ROOT / "VERSION"
        if version_file.exists():
            version = version_file.read_text().strip()
        else:
            version = "0.0.0"
        # git tag（版本号动态读取，不硬编码）
        sp.run(
            [
                "git",
                "tag",
                "-a",
                f"board-{task_id}",
                "-m",
                f"{version}: {task_id} 看板发布",
            ],
            cwd=ROOT,
            capture_output=True,
            timeout=10,
        )
        # git push tag
        push_r = sp.run(
            ["git", "push", "origin", f"board-{task_id}"],
            cwd=ROOT,
            capture_output=True,
            timeout=30,
        )
        if push_r.returncode != 0:
            _log.error("[kb] %s git push 失败 rc={push_r.returncode}", task_id)
            fail_log = ROOT / ".ccc" / "reports" / f"{task_id}.push-fail.md"
            fail_log.write_text(
                f"# {task_id} git push 失败\n\n"
                f"rc={push_r.returncode}\n"
                f"{push_r.stderr[:500]}\n"
            )
            continue

        # CHANGELOG.md 追加
        today_str = now_iso()[:10]
        changelog_path = ROOT / "CHANGELOG.md"
        # v0.28.0 (M-006): 写入前检查 task_id 是否已存在（kb_role 重试会重复追加）
        existing_text = ""
        if changelog_path.exists():
            try:
                existing_text = changelog_path.read_text()
            except OSError as exc:
                _log.warning("CHANGELOG read failed: %s", exc)
        if task_id in existing_text:
            _log.info("[kb] CHANGELOG 已包含 %s，跳过追加", task_id)
        else:
            entry = f"\n## [{version}] - {today_str}\n\n- {task_id}: {task.get('title', '')} 看板发布\n"
            new_text = (existing_text if existing_text else f"# CHANGELOG\n\n") + entry
            try:
                changelog_path.write_text(new_text)
                _log.info("[kb] ✓ CHANGELOG 追加 %s (%s)", task_id, version)
            except OSError as exc:
                _log.error("CHANGELOG 追加失败: %s", exc)

        # 收集 AGENTS.md 建议
        report_file = ROOT / ".ccc" / "reports" / f"{task_id}.report.md"
        all_suggestions.extend(
            _extract_agents_suggestions(report_file, task_id, source="dev")
        )
        verdict_file = ROOT / ".ccc" / "verdicts" / f"{task_id}.verdict.md"
        all_suggestions.extend(
            _extract_agents_suggestions(verdict_file, task_id, source="reviewer")
        )

        # 挪 released
        move_task(task_id, "verified", "released")
        moved.append(task_id)

    # 去重 → 写 pending-agents-suggestions.md
    if all_suggestions:
        seen: set[str] = set()
        unique: list[dict] = []
        for s in all_suggestions:
            key = s["content"].strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(s)

        pending_file = ROOT / ".ccc" / "pending-agents-suggestions.md"
        template_file = ROOT / "templates" / "pending-agents-suggestions.md"

        new_blocks: list[str] = []
        now_str = now_iso()[:10]
        for s in unique:
            block = (
                f"## 来源 task: {s['task_id']}\n\n"
                f"归档日期: {now_str}\n\n"
                f"### 来自 {s['source']}\n\n"
                f"{s['content']}\n\n"
                f"---\n"
            )
            new_blocks.append(block)

        new_content = "\n".join(new_blocks)
        if pending_file.exists():
            existing = pending_file.read_text().rstrip()
            pending_file.write_text(existing + "\n" + new_content + "\n")
        else:
            header = (
                template_file.read_text()
                if template_file.exists()
                else "# Pending AGENTS.md Suggestions\n\n"
            )
            pending_file.write_text(header + "\n" + new_content + "\n")
        _log.info("[kb] ✓ 收集 {len(unique)} 条 AGENTS.md 建议到 %s", pending_file)

    return {
        "role": "kb",
        "moved": moved,
        "suggestions_collected": len(all_suggestions),
        "counts": update_index(),
    }


# ═══════════════════════════════════════════
# audit 角色 (v0.22)
# ═══════════════════════════════════════════


WORKSPACES = cfg.audit_workspaces  # 复用 Config（v0.22 M7）


def _audit_recent_commits(workspace: str, since: str = "2 hours ago") -> str:
    """取 git log 短输出"""
    import subprocess as sp

    try:
        r = sp.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-merges"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout or ""
    except (sp.TimeoutExpired, OSError):
        return ""


def _audit_lint(workspace: str) -> tuple[str, str]:
    """跑 ruff + mypy 门禁。返回 (lint_output, mypy_output)。"""
    import subprocess as sp

    lint_out = ""
    mypy_out = ""
    pyproject = Path(workspace) / "pyproject.toml"
    if not pyproject.exists():
        return "", ""

    try:
        r = sp.run(
            ["ruff", "check", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        lint_out = (r.stdout or "") + (r.stderr or "")
    except (sp.TimeoutExpired, FileNotFoundError, OSError):
        pass

    try:
        r = sp.run(
            ["mypy", "src/"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        mypy_out = (r.stdout or "") + (r.stderr or "")
    except (sp.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return lint_out, mypy_out


def _audit_classify(
    workspace: str, recent_commits: str, lint_out: str, mypy_out: str
) -> dict:
    """启发式分类（v0.22 临时方案，v0.23 计划接入 Claude API）。

    返回 {"auto": [...], "review": [...], "decision": [...]}。

    v0.22 实现是字符串 contains 匹配，**非真正 AI**：
    - lint warning（无 "error" 字符串）→ auto
    - mypy "error:" → review
    - 暂无 decision 分类（保留字段给 v0.23 扩展）

    已知局限：可能误判某些 fixable 安全 warning 为 auto。v0.23 升级。
    """
    findings = {"auto": [], "review": [], "decision": []}

    # lint 问题 → auto（ruff --fix 可自动修）
    if lint_out and "error" not in lint_out.lower():
        for line in lint_out.split("\n"):
            line = line.strip()
            if line and not line.startswith("Found"):
                findings["auto"].append(f"lint: {line[:120]}")

    # mypy 错误 → review（需要类型注解修改）
    if mypy_out and "error:" in mypy_out:
        for line in mypy_out.split("\n")[:5]:
            line = line.strip()
            if line and "error:" in line:
                findings["review"].append(f"type: {line[:120]}")

    # 没有 commit → 无发现
    return findings


def _audit_post_backlog(workspace: str, items: list, category: str) -> int:
    """把 review/decision 类问题投到对应项目的 backlog。返回投出数。"""
    from datetime import datetime as _dt

    store = FileBoardStore(Path(workspace))
    date_str = _dt.now(timezone.utc).strftime("%Y%m%d-%H%M")
    now_iso_str = now_iso()
    posted = 0
    for i, item in enumerate(items):
        tid = sanitize_id(f"audit-{category}-{date_str}-{uuid.uuid4().hex[:8]}")
        title = item[:80]
        store.create_task(
            {
                "id": tid,
                "title": title,
                "description": f"[audit] {category} 类问题：\n\n{item}",
                "tags": ["audit", category],
                "status": "backlog",
                "created_at": now_iso_str,
                "updated_at": now_iso_str,
            },
            column="backlog",
        )
        posted += 1
    return posted


def _audit_write_report(
    workspace: str,
    findings: dict,
    commit_log: str,
    auto_fixed: list | None = None,
    mypy_raw: str = "",
    duration_seconds: float = 0.0,
) -> Path:
    """写审计报表到 {workspace}/.ccc/audit-reports/{date}.md"""
    from datetime import datetime as _dt

    name = Path(workspace).name
    date_str = _dt.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    report_dir = Path(workspace) / ".ccc" / "audit-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{date_str}.md"

    n_auto = len(findings.get("auto", []))
    n_review = len(findings.get("review", []))

    lines = [
        f"# Audit Report — {name} — {date_str}",
        "",
        "## Recent Commits (2h)",
        "```",
        commit_log or "(无变更)",
        "```",
        "",
        f"## Auto (可自动修) — {n_auto} 条",
    ]
    for item in findings.get("auto", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Auto-Fixed — {len(auto_fixed)} 条")
    for item in auto_fixed:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Review (需审查) — {n_review} 条")
    for item in findings.get("review", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Decision (需决策) — {len(findings.get('decision', []))} 条")
    for item in findings.get("decision", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Build Gate")
    lines.append(f"- ruff: {n_auto} auto / {n_review} review")
    lines.append("- mypy: 详见上方 review 段")
    if duration_seconds:
        lines.append(f"- 实测耗时: {duration_seconds:.1f}s")

    # mypy 原始输出附录（v0.22 N3：review 段只取前 5 行前 120 字符，完整输出在附录）
    if mypy_raw:
        lines.append("")
        lines.append("## 附录：mypy 原始输出")
        lines.append("```")
        lines.append(mypy_raw[:5000])  # 截断 5KB 防巨型输出
        lines.append("```")

    report_path.write_text("\n".join(lines))
    return report_path


def _audit_run_one(ws: str, since: str) -> dict:
    """单 workspace 审计流程：git log → lint/mypy → AI 分类 → auto fix → 投 backlog → 写报表

    v0.24.2: 抽出来作为可并发执行的单元，audit_role 用 ThreadPoolExecutor 并行调度。

    每个 ws 的写入路径（backlog / audit-reports）都是 per-workspace 文件名，
    多 ws 并发互不冲突；auto fix ruff 的 cwd 也是 ws 局部，无共享状态。
    """
    import subprocess as sp
    import time as _time

    _t_ws = _time.time()
    ws_path = Path(ws)
    if not (ws_path / ".git").exists():
        return {"workspace": ws, "status": "no_git", "findings": {}}

    # 1. git log
    commits = _audit_recent_commits(ws, since)
    if not commits.strip():
        return {"workspace": ws, "status": "no_changes", "findings": {}}

    # 2. lint + mypy 门禁
    lint_out, mypy_out = _audit_lint(ws)

    # 3. AI 分类（简化启发式）
    findings = _audit_classify(ws, commits, lint_out, mypy_out)

    # 4. auto 直接修（v0.22 边界：只对 tests/ + 配置/文档/杂项改，
    #    不动 src/ 业务代码。需要 D4 决策时再开 src 例外）
    auto_fixed = []
    if findings.get("auto"):
        try:
            sp.run(
                ["ruff", "check", "--fix", "--exclude", "src", "."],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=60,
            )
            auto_fixed = findings["auto"]
            findings["auto"] = []
        except (sp.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # 5. review/decision 投 backlog
    posted_review = _audit_post_backlog(ws, findings.get("review", []), "review")
    posted_decision = _audit_post_backlog(
        ws, findings.get("decision", []), "decision"
    )

    # 6. 写报表
    _elapsed_ws = _time.time() - _t_ws
    report_path = _audit_write_report(
        ws,
        findings,
        commits,
        auto_fixed=auto_fixed,
        mypy_raw=mypy_out,
        duration_seconds=_elapsed_ws,
    )

    return {
        "workspace": ws,
        "status": "audited",
        "auto_fixed": auto_fixed,
        "review_posted": posted_review,
        "decision_posted": posted_decision,
        "report": str(report_path),
        "duration_seconds": round(_elapsed_ws, 1),
    }


def audit_role(workspace: str | None = None, since: str = "2 hours ago") -> dict:
    """审计角色 (v0.22) — 跨 workspace 全项目扫描

    不同于 dev/reviewer/tester 等单 workspace 角色，audit 跨多个 workspace 调度
    （依赖 cfg.audit_workspaces）。调用方式：
    - CLI：python3 ccc-board.py audit
    - engine：_audit_should_run() 自动触发
    - main dispatch：单独分支（不在 ROLES 字典中）

    流程: 全项目扫描 → AI 分类 → auto 直接修 / review/decision 投 backlog → 写报表

    v0.24.2: 多 workspace 并行化
      - 单 workspace（指定 ws）：串行执行（原行为）
      - 多 workspace：ThreadPoolExecutor 并发跑，单 ws 处理抽到 _audit_run_one
      - 并发度：min(len(WORKSPACES), 4)，避免 ruff/mypy 进程爆栈

    Args:
        workspace: 指定 workspace；None = 扫所有 WORKSPACES
        since: git log 时间窗口（默认 2h）
    """
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    _t0 = _time.time()
    targets = [workspace] if workspace else list(WORKSPACES)
    results = []

    if len(targets) <= 1:
        # 单 ws：保持原串行路径，无线程开销
        if targets:
            results.append(_audit_run_one(targets[0], since))
    else:
        # v0.24.2: 多 ws 并发
        # v0.24.3: OOM 防护 — max_workers=2 避免 4×(ruff+mypy) 同时跑爆内存
        max_workers = min(len(targets), 2)
        # v0.24.3: 单 ws timeout — 单卡死不能阻塞整个 audit 角色
        ws_timeout = 120
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_audit_run_one, ws, since): ws for ws in targets
            }
            for fut, ws in futures.items():
                try:
                    results.append(fut.result(timeout=ws_timeout))
                except FuturesTimeoutError:
                    results.append(
                        {"workspace": ws, "status": "timeout",
                         "error": f"timeout after {ws_timeout}s"}
                    )
                except Exception as exc:
                    results.append(
                        {"workspace": ws, "status": "error", "error": str(exc)}
                    )

    # 记录运行时间
    _elapsed = _time.time() - _t0
    from datetime import datetime as _dt

    ws_slug = Path(str(workspace)).name if workspace else "CCC"
    last_run = Path.home() / ".ccc" / f"audit-last-run.{ws_slug}.json"
    last_run.parent.mkdir(parents=True, exist_ok=True)
    last_run.write_text(
        json.dumps(
            {
                "workspace": str(workspace) if workspace else "CCC",
                "last_run": _dt.now(timezone.utc).isoformat(),
                "results_count": len(results),
                "duration_seconds": round(_elapsed, 1),
            },
            ensure_ascii=False,
        )
        + "\n"
    )

    return {"role": "audit", "results": results, "duration_seconds": round(_elapsed, 1)}


def regress_role() -> dict:
    """回测工程师: 每日扫 released → py_compile + git diff → 发现回归→建 bug"""
    import subprocess as sp
    from datetime import date

    results = {"checked": 0, "passed": 0, "failed": 0, "regressions": []}
    tasks = list_tasks("released")
    if not tasks:
        return {"role": "regress", "info": "无已发布任务", "results": results}

    today = date.today().isoformat()
    scripts_dir = ROOT / "scripts"
    # v0.28.0 (N-004): scripts_dir 不存在时 rglob 返回空（不抛错）→ py_ok=True 假阳性。
    # 显式检查目录存在，缺失则降级：跳过 py_compile 标记 unknown，循环内按 unknown 处理。
    py_files: list[Path] = []
    py_check_available = False
    if scripts_dir.is_dir():
        py_files = list(scripts_dir.rglob("*.py"))
        py_check_available = True
    else:
        _log.warning(
            "regress: scripts_dir 不存在 (%s) — 跳过 py_compile 检查",
            scripts_dir,
        )

    # v0.28.0 (M-004): py_compile 是项目级检查，所有 .py 文件语法问题与 task 无关。
    # 提到循环外，只跑一次，结果在循环内复用。
    py_ok = True
    failed_py: list[Path] = []
    for py in py_files:
        r = sp.run(
            ["python3", "-m", "py_compile", str(py)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            py_ok = False
            failed_py.append(py)
    if not py_ok:
        _log.warning(
            "regress: 项目级 py_compile 失败 %d 个文件: %s",
            len(failed_py),
            [p.name for p in failed_py[:5]],
        )

    for task in tasks:
        tid = task["id"]
        results["checked"] += 1

        # 1. py_compile — 复用上面的项目级结果
        # v0.28.0 (N-004): scripts_dir 不存在时 py_check_available=False，
        # 跳过 py_compile 检查（task_py_ok=True 不归咎 task，但记 skipped_py_check）。
        task_py_ok = py_ok
        if not py_check_available:
            results.setdefault("skipped_py_check", 0)
            results["skipped_py_check"] += 1

        # 2. git diff 检查是否代码被意外改过
        diff_ok = True
        r = sp.run(
            ["git", "diff", "HEAD", "--stat"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.stdout.strip():
            diff_ok = False

        if task_py_ok and diff_ok:
            results["passed"] += 1
            _log.info("[regress] ✓ %s", tid)
        else:
            results["failed"] += 1
            today_compact = date.today().strftime("%Y%m%d")
            bug_id = f"regression-{tid}-{today_compact}-{results['failed']}"
            bug_title = f"回归: {task.get('title', tid)} ({today})"
            bug_desc = f"原任务 {tid} 在 {today} 回测失败\n"
            if not task_py_ok:
                bug_desc += "- py_compile 失败：代码有语法错误\n"
            if not diff_ok:
                bug_desc += "- git diff 非空：代码有意外改动\n"
            create_task({"id": bug_id, "title": bug_title, "description": bug_desc})
            results["regressions"].append(bug_id)
            _log.info("[regress] ✗ %s → %s", tid, bug_id)
            # 把原任务移回 backlog 并加 regression 标签
            src_path = BOARD / "released" / f"{tid}.jsonl"
            if src_path.exists():
                _lines = src_path.read_text().split("\n")
                for _i, _line in enumerate(_lines):
                    _ls = _line.strip()
                    if not _ls:
                        continue
                    try:
                        _obj = json.loads(_ls)
                        _tags = _obj.get("tags", [])
                        if "regression" not in _tags:
                            _tags.append("regression")
                        _obj["tags"] = _tags
                        _obj["updated_at"] = now_iso()
                        _lines[_i] = json.dumps(_obj, ensure_ascii=False)
                        break
                    except json.JSONDecodeError:
                        pass
                src_path.write_text("\n".join(_lines))
            move_task(tid, "released", "backlog")
            # macOS 桌面通知
            subprocess.run(
                [
                    "bash",
                    str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                    "L2",
                    bug_title,
                    bug_desc[:200],
                ],
                capture_output=True,
                timeout=10,
            )

    # 写回测日报
    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"regression-{today}.md"
    report.write_text(
        f"# 回测日报 {today}\n\n"
        f"- 检查任务: {results['checked']}\n"
        f"- 通过: {results['passed']}\n"
        f"- 失败: {results['failed']}\n"
        f"- 新建回归 bug: {len(results['regressions'])}\n"
    )
    return {"role": "regress", "results": results, "report": str(report)}


def get_timeline(task_id: Optional[str] = None) -> list[dict]:
    """读取 timeline 事件（委托 FileBoardStore）"""
    return store.get_timeline(task_id)


def approve_agents() -> dict:
    """人类审批: 读 pending-agents-suggestions.md → 追加到 .ccc/AGENTS.md"""
    import re

    pending_file = ROOT / ".ccc" / "pending-agents-suggestions.md"
    if not pending_file.exists():
        msg = f"[approve-agents] 无待审批建议文件: {pending_file}"
        _log.info(msg)
        return {"role": "approve-agents", "approved": 0, "error": "no pending file"}

    content = pending_file.read_text()

    # 分割：migration_idx 之前是建议块，之后是迁移记录
    migration_idx = content.find("\n## 迁移记录")
    suggestions_text = content[:migration_idx] if migration_idx != -1 else content

    # 按 ## 来源 task: 分割每个建议块
    raw_blocks = re.split(r"\n(?=## 来源 task:)", suggestions_text)
    suggestions = []
    for block in raw_blocks:
        block = block.strip()
        if not block or block.startswith("# Pending") or block.startswith("> "):
            continue

        task_m = re.search(r"## 来源 task:\s*(\S+)", block)
        source_m = re.search(r"### 来自\s+(\w+)", block)
        if not task_m or not source_m:
            continue
        task_id = task_m.group(1)
        source = source_m.group(1)

        # 提取 ### 来自 <source> 之后到 --- 之前的内容
        after_source = block.split(f"### 来自 {source}")[-1].strip()
        content_text = re.split(r"\n---|\n## ", after_source)[0].strip()
        if content_text:
            suggestions.append(
                {
                    "task_id": task_id,
                    "source": source,
                    "content": content_text,
                }
            )

    if not suggestions:
        _log.info("[approve-agents] 无新建议需审批")
        return {"role": "approve-agents", "approved": 0, "info": "nothing new"}

    # 写入/追加 .ccc/AGENTS.md
    agents_file = ROOT / ".ccc" / "AGENTS.md"
    if not agents_file.exists():
        template_file = ROOT / "templates" / "AGENTS.md"
        if template_file.exists():
            agents_content = template_file.read_text()
            profile_file = ROOT / ".ccc" / "profile.md"
            if profile_file.exists():
                pf = profile_file.read_text()
                name_m = re.search(r"项目名[：:]\s*(.+)", pf)
                if name_m:
                    agents_content = agents_content.replace(
                        "{{PROJECT_NAME}}", name_m.group(1).strip()
                    )
            agents_content = agents_content.replace("{{PROJECT_PATH}}", str(ROOT))
            agents_content = agents_content.replace(
                "{{PRIMARY_LANGUAGE}}", "Python+Bash"
            )
            agents_content = agents_content.replace("{{DATE}}", now_iso()[:10])
        else:
            agents_content = "# CCC Agent Guide\n"
        agents_file.write_text(agents_content + "\n\n## AGENTS.md 建议积累\n\n")
        _log.info("[approve-agents] 创建 %s", agents_file)

    existing = agents_file.read_text().rstrip()
    new_entries = []
    for s in suggestions:
        entry = f"### 来自 {s['source']} ({s['task_id']})\n\n{s['content']}\n"
        new_entries.append(entry)
    agents_file.write_text(existing + "\n" + "\n".join(new_entries) + "\n")

    # 从 pending 文件中移除已审批的建议块（保留 header + 迁移记录）
    now = now_iso()[:10]
    n = len(suggestions)
    # 提取 header（截止到第一个建议块之前）
    header_lines = []
    for line in content.split("\n"):
        if line.strip().startswith("## 来源 task:") or line.strip().startswith("---"):
            break
        header_lines.append(line)
    header = "\n".join(header_lines).rstrip()

    migration_line = f"| {now} | approve-agents | ✅ (已写入 {n} 条) | 自动审批 |\n"
    if migration_idx != -1:
        existing_migration = content[migration_idx:].rstrip()
        pending_file.write_text(
            header + "\n\n" + existing_migration + "\n" + migration_line
        )
    else:
        pending_file.write_text(
            header
            + "\n\n## 迁移记录\n\n"
            + "| 日期 | 迁移人 | 写入 AGENTS.md? | 备注 |\n"
            + "|------|--------|----------------|------|\n"
            + migration_line
        )

    _log.info("[approve-agents] ✓ %s 条建议已写入 %s", n, agents_file)
    return {"role": "approve-agents", "approved": n, "file": str(agents_file)}


# ═══════════════════════════════════════════
# 引擎辅助函数 (v0.20.1)
# ═══════════════════════════════════════════


def dev_role_launch(task_id: str) -> dict:
    """引擎用：启 opencode 执行 task，返回启动结果

    1. 确认 task 在 planned，有 plan+phases
    2. 挪 planned → in_progress
    3. 启 opencode-runner.sh（后台进程）
    4. 不等待，立即返回
    """

    task_id = sanitize_id(task_id)
    planned = list_tasks("planned")
    task = next((t for t in planned if t["id"] == task_id), None)
    if not task:
        return {"error": f"task '{task_id}' not in planned", "task_id": task_id}

    cplan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    cphases = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not cplan.exists() or not cphases.exists():
        _quarantine(task_id, "engine: 缺 plan 或 phases 文件")
        return {
            "error": f"task '{task_id}' missing plan/phases, quarantined",
            "task_id": task_id,
        }

    move_task(task_id, "planned", "in_progress")

    # 从 phases.json 读 timeout
    timeout_s = _load_timeout(cphases, default=cfg.default_timeout)
    # v0.24.3: 用 _current_running_phase() 决定当前应跑哪个 phase，而不是硬编码 -p1。
    # phases.json 可能尚未标 in_progress（launch 是入口），退回到 pending/blocked 中的第一个 phase。
    cur_phase = _current_running_phase(task_id)
    phase_id = f"{task_id}-p{cur_phase}"
    plan_content = cplan.read_text()
    prompt = (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## Plan\n\n{plan_content}\n\n"
        f"## 完成定义\n"
        f"1. 实现所有需求\n"
        f"2. 跑对应的测试（如有）\n"
        f"3. 提交一个 commit（message 以 {task_id} 开头）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 plan 文件白名单\n"
    )

    pids_dir = ROOT / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)

    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    import subprocess as sp

    proc = sp.Popen(
        [
            str(CCC_HOME / "scripts" / "opencode-runner.sh"),
            task_id,
            str(CCC_HOME),  # $2: CCC_HOME（opencode-exec.py 所在目录）
            str(ROOT),  # $3: ROOT_DIR（结果文件写到 workspace）
            "--phase",
            phase_id,
            "--prompt",
            prompt_file,
            "--timeout",
            str(timeout_s),
            "--cwd",
            str(ROOT),  # opencode 工作目录 = workspace
        ],
        start_new_session=True,
    )
    pids_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
    _log.info("[engine] %s launched PID={proc.pid}", task_id)

    return {"ok": True, "task_id": task_id, "pid": proc.pid}


def dev_role_relaunch(task_id: str) -> dict:
    """引擎用：失败重试时重新启 opencode（task 已在 in_progress 不挪列）

    与 dev_role_launch 的区别：
    - 不检查 planned，直接读 plan+phases
    - 不挪列（已在 in_progress）
    - 清理旧的 .done/exitcode 后重新启动
    """

    task_id = sanitize_id(task_id)
    cplan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    cphases = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not cplan.exists() or not cphases.exists():
        _quarantine(task_id, "engine relaunch: 缺 plan 或 phases 文件")
        return {"error": f"task '{task_id}' missing plan/phases", "task_id": task_id}

    # 清理旧的标记文件
    pids_dir = ROOT / ".ccc" / "pids"
    for suffix in [".done", ".exitcode", ".pid", ".prompt.md", ".result.json"]:
        f = pids_dir / f"{task_id}{suffix}"
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass
        # 也检查 reports/
        f2 = ROOT / ".ccc" / "reports" / f"{task_id}{suffix}"
        if f2.exists():
            try:
                f2.unlink()
            except OSError:
                pass

    timeout_s = _load_timeout(cphases, default=cfg.default_timeout)
    # v0.24.3: 重启也用 _current_running_phase() 定位当前 phase
    cur_phase = _current_running_phase(task_id)
    phase_id = f"{task_id}-p{cur_phase}"
    plan_content = cplan.read_text()
    prompt = (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## Plan\n\n{plan_content}\n\n"
        f"## 完成定义\n"
        f"1. 实现所有需求\n"
        f"2. 跑对应的测试（如有）\n"
        f"3. 提交一个 commit（message 以 {task_id} 开头）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 plan 文件白名单\n"
    )

    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)

    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    import subprocess as sp

    proc = sp.Popen(
        [
            str(CCC_HOME / "scripts" / "opencode-runner.sh"),
            task_id,
            str(CCC_HOME),  # $2: CCC_HOME
            str(ROOT),  # $3: ROOT_DIR
            "--phase",
            phase_id,
            "--prompt",
            prompt_file,
            "--timeout",
            str(timeout_s),
            "--cwd",
            str(ROOT),
        ],
        start_new_session=True,
    )
    pids_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
    _log.info("[engine] %s relaunched PID={proc.pid}", task_id)

    return {"ok": True, "task_id": task_id, "pid": proc.pid}


def dev_role_check_complete(task_id: str) -> dict:
    """引擎用：检查 task 的 opencode 是否完成

    返回:
      {"status": "running"} — 仍在跑
      {"status": "success"} — 完成，已从 in_progress 移到 testing
      {"status": "failed", "retry": N} — 可重试
      {"status": "quarantined"} — 重试耗尽，已隔离
      {"status": "not_found"} — task 不在 in_progress
    """
    task_id = sanitize_id(task_id)
    in_prog = list_tasks("in_progress")
    if not any(t["id"] == task_id for t in in_prog):
        return {"status": "not_found", "task_id": task_id}

    done_path = ROOT / ".ccc" / "pids" / f"{task_id}.done"
    if not done_path.exists():
        # G4: 检查 PID 是否存活（重启后 .pid 可能指向已死进程）
        pid_path = ROOT / ".ccc" / "pids" / f"{task_id}.pid"
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text().strip())
                os.kill(pid, 0)  # 信号 0 = 只检查存活
            except (ValueError, OSError, ProcessLookupError):
                # PID 不存在 → 清理标记文件，返回 failed 让 engine 重启
                for f in [pid_path, done_path, ROOT / ".ccc" / "pids" / f"{task_id}.exitcode"]:
                    try:
                        f.unlink()
                    except OSError:
                        pass
                _log.error("[engine] %s G4: PID 已死，标记为失败", task_id)
                return {"status": "failed", "retry": 0, "task_id": task_id}
        return {"status": "running", "task_id": task_id}

    exitcode_path = ROOT / ".ccc" / "pids" / f"{task_id}.exitcode"
    result_path = ROOT / ".ccc" / "reports" / f"{task_id}.result.json"
    exit_code = exitcode_path.read_text().strip() if exitcode_path.exists() else "?"
    result_raw = result_path.read_text() if result_path.exists() else "{}"

    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_dir.joinpath(f"{task_id}.report.md").write_text(
        f"# {task_id} 执行报告\n\n## 信息\n- Phase: {task_id}-p1\n"
        f"- 退出码: {exit_code}\n\n## 输出\n```\n{result_raw[:2000]}\n```\n"
    )

    # 标记文件列表（用于清算）
    marker_files = [
        done_path,
        exitcode_path,
        ROOT / ".ccc" / "pids" / f"{task_id}.pid",
        ROOT / ".ccc" / "pids" / f"{task_id}.prompt.md",
        result_path,
    ]

    if exit_code == "0":
        # 成功：清标记文件 + 挪列
        for p in marker_files:
            try:
                p.unlink()
            except OSError:
                pass
        move_task(task_id, "in_progress", "testing")
        _log.info("[engine] %s ✓ moved to testing", task_id)
        return {"status": "success", "task_id": task_id}
    else:
        # 失败：读 retry 计数，保留 .done 文件供 engine 下次 check
        phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
        retry = 0
        try:
            if phases_file.exists():
                with open(phases_file) as _pf:
                    for _line in _pf:
                        _line = _line.strip()
                        if not _line or not _line.startswith("{"):
                            continue
                        phase = json.loads(_line)
                        if "schema_version" in phase:
                            continue
                        retry = phase.get("retry", 0)
                        break
        except (json.JSONDecodeError, OSError):
            pass

        retry += 1
        # 更新 phases.json retry 计数
        try:
            if phases_file.exists():
                lines = phases_file.read_text().split("\n")
                for i, _line in enumerate(lines):
                    _ls = _line.strip()
                    if not _ls or not _ls.startswith("{"):
                        continue
                    try:
                        phase = json.loads(_ls)
                        if "schema_version" in phase:
                            continue
                        phase["retry"] = retry
                        lines[i] = json.dumps(phase, ensure_ascii=False)
                        break
                    except json.JSONDecodeError:
                        pass
                phases_file.write_text("\n".join(lines))
        except OSError:
            pass

        if retry >= MAX_RETRY:
            # 重试耗尽：清理标记 + 异常隔离
            for p in marker_files:
                try:
                    p.unlink()
                except OSError:
                    pass
            # v0.24: 标记 phase failed + 触发失败传染链路
            _mark_phase_failed(task_id, phase_id=_current_running_phase(task_id))
            failure_summary = _check_phase_failures(task_id)
            if failure_summary.get("all_failed_or_skipped"):
                # 所有 phase 都失败 → task 移到 abnormal（不进 verified）
                _move_task_to_abnormal_if_all_terminal_failed(task_id)
                _quarantine(
                    task_id,
                    f"engine: 重试{MAX_RETRY}次全部失败，"
                    f"下游 phase {failure_summary['skipped']} 自动跳过 → abnormal",
                )
            else:
                _quarantine(task_id, f"engine: 重试{MAX_RETRY}次全部失败，隔离")
            _log.error(
                "[engine] %s retry=%d >= %d, quarantined (skipped_downstream=%d)",
                task_id,
                retry,
                MAX_RETRY,
                failure_summary["skipped"],
            )
            return {"status": "quarantined", "task_id": task_id}
        else:
            # 保留 .done 在磁盘，engine 下次 check 时看到 failed 状态就会 relaunch
            _log.info("[engine] %s rc=%s retry=%s/%s", task_id, exit_code, retry, MAX_RETRY)
            return {"status": "failed", "task_id": task_id, "retry": retry}


ROLES = {
    "product": product_role,
    "dev": dev_role,
    "reviewer": reviewer_role,
    "tester": tester_role,
    "ops": ops_role,
    "kb": kb_role,
    "regress": regress_role,
    "approve-agents": approve_agents,
}


def batch_process(lines: list[dict]) -> dict:
    """批量处理 create/move 操作

    每行格式:
      {"action":"create","id":"...","title":"...","column":"backlog",...}
      {"action":"move","id":"...","from":"backlog","to":"planned"}
    """
    results: dict = {"created": [], "moved": [], "errors": []}
    for i, op in enumerate(lines):
        action = op.get("action", "")
        task_id = op.get("id", "")
        try:
            if action == "create":
                column = op.get("column", "backlog")
                ok = create_task(op, column=column)
                if ok:
                    results["created"].append(task_id)
                else:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "create failed"}
                    )
            elif action == "move":
                from_col = op.get("from", "")
                to_col = op.get("to", "")
                if not from_col or not to_col:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "missing from/to"}
                    )
                    continue
                ok = move_task(task_id, from_col, to_col)
                if ok:
                    results["moved"].append(task_id)
                else:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "move failed"}
                    )
            else:
                results["errors"].append(
                    {"line": i, "id": task_id, "error": f"unknown action '{action}'"}
                )
        except Exception as e:  # debug
            results["errors"].append({"line": i, "id": task_id, "error": str(e)})
    results["counts"] = update_index()
    return results


def main():
    ap = argparse.ArgumentParser(description="CCC 任务看板 7 角色核心")
    ap.add_argument(
        "role",
        nargs="?",
        choices=list(ROLES.keys()) + ["index", "audit"],
        help="角色名 或 'index'",
    )
    ap.add_argument(
        "--batch", action="store_true", help="批量模式（从 stdin 读 JSONL）"
    )
    ap.add_argument("--file", type=str, help="批量模式输入文件（替代 stdin）")
    ap.add_argument(
        "--promote",
        type=str,
        help="product: 处理指定 backlog task → 写 plan/phases → 挪 planned",
    )
    ap.add_argument("--json", action="store_true", help="JSON 输出（角色模式下）")
    args = ap.parse_args()

    if args.batch:
        fp = open(args.file) if args.file else sys.stdin
        lines = []
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError as e:
                _log.error("[board] batch skip invalid JSON: %s", e)
        if args.file:
            fp.close()
        result = batch_process(lines)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.role == "index":
        print(json.dumps(update_index(), indent=2, ensure_ascii=False))
        return

    if args.role == "audit":
        result = audit_role()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.role:
        ap.print_help()
        sys.exit(1)

    if args.promote:
        if args.role != "product":
            _log.error("[board] --promote 仅适用于 product 角色")
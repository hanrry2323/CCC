"""board.phase — phases.json 加载 / 依赖解析 / 失败传染（从 ccc-board 拆出）。"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from _config import get_logger
from _executor import _sanitized_env
from _board_store import _atomic_write as _store_atomic_write
from _utils import now_iso

from board.context import get_workspace, ccc_home
from board.store_ops import move_task

_log = get_logger("board.phase")
CCC_HOME = ccc_home()

# v0.24: phases.json 加载 + 依赖解析
PHASE_TERMINAL_OK = {"done", "verified", "skipped"}
PHASE_TERMINAL_FAIL = {"failed"}

# unresolved_dep / phase_cycle 告警去重窗口（秒）— 同 signature 不重复写盘/桌面通知
_WARN_DEDUP_SEC = 3600


def _coerce_phase_id(value) -> int | None:
    """把 phase / depends_on 元素规范成 int。

    LLM 常产出字符串 \"1\"；若不强制转换，by_id 用 int 键时 lookup 失败，
    会被误判为「引用了不存在的 phase_id」并刷 L2 通知。
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _phase_index(phases: list[dict]) -> dict[int, dict]:
    """phase_id(int) → phase dict；重复 id 保留后者。"""
    by_id: dict[int, dict] = {}
    for p in phases:
        pid = _coerce_phase_id(p.get("phase"))
        if pid is None:
            continue
        by_id[pid] = p
    return by_id


def _normalized_deps(phase: dict) -> list[int]:
    out: list[int] = []
    for dep in phase.get("depends_on") or []:
        d = _coerce_phase_id(dep)
        if d is not None:
            out.append(d)
    return out


def _load_phases(task_id: str, ws: Path | None = None) -> list[dict]:
    """v0.24: 加载 phases.jsonl 每行一个 phase dict（跳过 schema_version 行）。

    Args:
        task_id: 任务 ID
        ws: workspace 路径。为 None 时回退到 get_workspace()（兼容旧调用者）。

    返回按 phase 编号排序的 list，元素为 phase dict。
    文件不存在或解析失败返回空 list。
    """
    base = ws if ws else get_workspace()
    phases_file = base / ".ccc" / "phases" / f"{task_id}.phases.json"
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
    out.sort(key=lambda p: _coerce_phase_id(p.get("phase")) or 0)
    return out


def _detect_phase_cycle(phases: list[dict]) -> list[list[int]]:
    """v0.25.1: 检测 phases.json 中的循环依赖。

    用 DFS 三色标记（WHITE=未访问 / GRAY=在栈上 / BLACK=已完成）。
    返回所有循环路径（每条路径是 phase_id 列表）。

    注：函数内静默检测，不抛异常。Engine 在 _resolve_phase_dependencies
    调用时拿到 cycle 列表，把环上 phase 标 skipped + 写 warnings.json。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    by_id = _phase_index(phases)
    color: dict[int, int] = {pid: WHITE for pid in by_id}
    cycles: list[list[int]] = []

    def dfs(node: int, stack: list[int]) -> None:
        color[node] = GRAY
        stack.append(node)
        for dep_id in _normalized_deps(by_id.get(node, {})):
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


def _collect_unresolved_deps(by_id: dict[int, dict]) -> dict[int, list[int]]:
    """phase_id → 缺失的 depends_on id 列表。"""
    unresolved: dict[int, list[int]] = {}
    for pid, phase in by_id.items():
        for dep_id in _normalized_deps(phase):
            if dep_id not in by_id:
                unresolved.setdefault(pid, []).append(dep_id)
    return unresolved


def _warning_signature(wtype: str, payload: dict) -> str:
    if wtype == "unresolved_dep":
        return f"unresolved_dep:{json.dumps(payload.get('missing'), sort_keys=True)}"
    if wtype == "phase_cycle":
        return f"phase_cycle:{json.dumps(payload.get('cycles'), sort_keys=True)}"
    return f"{wtype}:{json.dumps(payload, sort_keys=True, default=str)}"


def _recent_warning_exists(existing: list, signature: str, *, within_sec: int) -> bool:
    """同 signature 在窗口内已写过 → True（跳过）。"""
    import time
    from datetime import datetime

    now = time.time()
    for w in reversed(existing[-50:]):
        if not isinstance(w, dict):
            continue
        wtype = w.get("type") or ""
        sig = _warning_signature(wtype, w)
        if sig != signature:
            continue
        ts = w.get("detected_at") or ""
        try:
            # 兼容 +08:00 / Z
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age = now - dt.timestamp()
            if age < within_sec:
                return True
        except (TypeError, ValueError):
            return True  # 无法解析时间戳时保守去重
    return False


def _emit_phase_graph_warnings(
    cycles: list[list[int]],
    unresolved: dict[int, list[int]],
    *,
    notify: bool = True,
) -> None:
    """写 warnings.json +（可选）L2 通知；同 signature 1h 内去重。"""
    if not cycles and not unresolved:
        return
    try:
        warnings_file = get_workspace() / ".ccc" / "warnings.json"
    except Exception:
        return
    try:
        existing: list = []
        if warnings_file.exists():
            try:
                existing = json.loads(warnings_file.read_text())
                if not isinstance(existing, list):
                    existing = []
            except json.JSONDecodeError:
                existing = []

        changed = False
        if cycles:
            payload = {"type": "phase_cycle", "cycles": cycles, "detected_at": now_iso()}
            sig = _warning_signature("phase_cycle", payload)
            if not _recent_warning_exists(existing, sig, within_sec=_WARN_DEDUP_SEC):
                existing.append(payload)
                changed = True

        if unresolved:
            payload = {
                "type": "unresolved_dep",
                "missing": {str(k): v for k, v in unresolved.items()},
                "detected_at": now_iso(),
            }
            sig = _warning_signature("unresolved_dep", payload)
            if not _recent_warning_exists(existing, sig, within_sec=_WARN_DEDUP_SEC):
                existing.append(payload)
                changed = True
                if notify:
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
                            env=_sanitized_env(),
                            timeout=5,
                        )
                    except Exception as exc:
                        _log.debug("ccc-notify.sh L2 unresolved_dep failed: %s", exc)

        if changed:
            warnings_file.parent.mkdir(parents=True, exist_ok=True)
            warnings_file.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2)
            )
    except OSError as exc:
        _log.debug("write warnings.json (phase graph) failed: %s", exc)


def _resolve_phase_dependencies(
    phases: list[dict],
    *,
    emit_warnings: bool = False,
) -> tuple[set[int], set[int], set[int]]:
    """v0.24: 解析 phase 依赖关系。

    对每个 phase 检查 depends_on 列表中所有前置 phase 的状态：
    - 所有依赖状态 ∈ {done, verified, skipped} → 本 phase 可执行 (executable)
    - 任意依赖状态 ∈ {failed} → 本 phase 跳过 (skipped)
    - 其他依赖未达终态 → 本 phase 阻塞 (blocked）

    v0.25.1: 加循环依赖检测。环上 phase 全部归 skipped（强失败隔离）。
    v0.42.4: 默认纯函数（不写盘/不通知）；emit_warnings=True 时去重后告警。
             phase/depends_on 强制 int，避免 str/int 误判「不存在」。

    Returns:
        (executable_phase_ids, blocked_phase_ids, skipped_phase_ids)
    """
    by_id = _phase_index(phases)

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
        if (
            status in PHASE_TERMINAL_OK
            or status in PHASE_TERMINAL_FAIL
            or status == "in_progress"
        ):
            continue

        # v0.25.1: 环上节点直接 skipped（强失败隔离）
        if pid in cycle_nodes:
            skipped.add(pid)
            continue

        deps = _normalized_deps(phase)
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

    if emit_warnings:
        unresolved = _collect_unresolved_deps(by_id)
        _emit_phase_graph_warnings(cycles, unresolved, notify=True)

    return executable, blocked, skipped


def _apply_phase_status_updates(
    task_id: str, blocked: set[int], skipped: set[int]
) -> None:
    """v0.24: 把解析出的 blocked/skipped 状态写回 phases.jsonl。

    双向同步（Engine 每 tick 调用）：
    - pending → skipped（依赖失败）
    - pending → blocked（依赖未满足）
    - blocked → pending（依赖已满足，下一轮可执行）
    已 in_progress/done/verified/failed/skipped 的不碰。

    v0.28.1: 改用 _store_atomic_write（temp+replace）替代 in-place truncate 写。
    """
    phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        return
    try:
        lines = phases_file.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        _log.warning("read phases for status update failed %s: %s", task_id, e)
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
        pid_i = _coerce_phase_id(pid)
        if status == "pending":
            if pid_i in skipped:
                obj["status"] = "skipped"
                changed = True
            elif pid_i in blocked:
                obj["status"] = "blocked"
                changed = True
        elif status == "blocked":
            if pid_i not in blocked and pid_i not in skipped:
                obj["status"] = "pending"
                changed = True
        new_lines.append(json.dumps(obj, ensure_ascii=False))
    if changed:
        payload = "\n".join(new_lines) + "\n"
        try:
            _store_atomic_write(phases_file, payload)
        except OSError as e:
            _log.warning("atomic write phases status failed %s: %s", task_id, e)


def _current_running_phase(task_id: str) -> int:
    """v0.24: 找 task 当前正在跑的 phase 编号（status=in_progress 的 phase）。

    没有 in_progress phase 时返回第一个可执行的 pending/blocked phase（跳过 skipped）。
    """
    phases = _load_phases(task_id)
    for p in phases:
        if p.get("status") == "in_progress":
            return p.get("phase", 1)
    executable, blocked, _skipped = _resolve_phase_dependencies(phases)
    if executable:
        return min(executable)
    candidates = [p for p in phases if p.get("status") in ("pending", "blocked")]
    if candidates:
        return candidates[0].get("phase", 1)
    return 1


def _mark_phase_done(task_id: str, phase_id: int) -> None:
    """v0.38: 标记某个 phase 为 done（phase 成功完成时调用）。"""
    phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
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
            obj["status"] = "done"
            changed = True
        new_lines.append(json.dumps(obj, ensure_ascii=False))
    if changed:
        try:
            _store_atomic_write(phases_file, "\n".join(new_lines) + "\n")
        except OSError as e:
            _log.warning("mark phase done failed %s p=%s: %s", task_id, phase_id, e)


def _mark_phase_failed(task_id: str, phase_id: int) -> None:
    """v0.24: 标记某个 phase 为 failed（quarantine 时调用）。

    仅当 phase 还在 pending/blocked/in_progress 时才改为 failed；
    已 done/verified/skipped/failed 不动。
    """
    phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
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
    4. v0.31 (P0.1): 多轮 tick 不收敛（>= PHASE_MAX_ENGINE_ITER）
       → 标 unresolvable，不再 skip 掩盖
    5. 返回 {"executable": [...], "blocked": [...], "skipped": [...],
            "all_terminal": bool, "all_failed_or_skipped": bool, "engine_iter": int,
            "unresolvable": bool}

    Engine 在每次 dev 完成后调用一次，让失败传染链路在多轮 tick 中收敛。
    """
    phases = _load_phases(task_id)
    if not phases:
        return {
            "executable": [],
            "blocked": [],
            "skipped": [],
            "all_terminal": False,
            "all_failed_or_skipped": False,
            "engine_iter": 0,
            "unresolvable": False,
        }

    executable, blocked, skipped = _resolve_phase_dependencies(phases)
    _apply_phase_status_updates(task_id, blocked, skipped)

    # v0.24.3: writeback 后必须 reload，否则返回值基于陈旧内存状态计算。
    phases = _load_phases(task_id)
    # 仅第二次 emit（去重），避免同 tick 双写 + 桌面通知刷屏
    executable, blocked, skipped = _resolve_phase_dependencies(
        phases, emit_warnings=True
    )
    # 回报磁盘真实状态（已写回的 skipped/blocked 不再出现在 resolve 的新增集合里）
    skipped_on_disk = {
        pid
        for p in phases
        if p.get("status") == "skipped"
        and (pid := _coerce_phase_id(p.get("phase"))) is not None
    }
    blocked_on_disk = {
        pid
        for p in phases
        if p.get("status") == "blocked"
        and (pid := _coerce_phase_id(p.get("phase"))) is not None
    }

    all_terminal = all(
        p.get("status") in (PHASE_TERMINAL_OK | PHASE_TERMINAL_FAIL) for p in phases
    )
    all_failed_or_skipped = all(
        p.get("status") in ("failed", "skipped") for p in phases
    )

    # v0.25.1: 多轮 tick 不收敛强失败（CHANGELOG v0.24.4:94 P1）
    # v0.31 (P0.1): 不再 force-converge（skip 掩盖），改 unresolvable 标记
    engine_iter = _read_engine_iter(task_id)
    unresolvable = False
    if not all_terminal:
        engine_iter += 1
        _write_engine_iter(task_id, engine_iter)
        if engine_iter >= PHASE_MAX_ENGINE_ITER:
            unresolvable = True
            # 写 unresolvable 诊断到 warnings.json
            unresolved_phases = [
                p.get("phase")
                for p in phases
                if p.get("status") not in (PHASE_TERMINAL_OK | PHASE_TERMINAL_FAIL)
                and p.get("phase") is not None
            ]
            try:
                warnings_file = get_workspace() / ".ccc" / "warnings.json"
                existing = []
                if warnings_file.exists():
                    try:
                        existing = json.loads(warnings_file.read_text())
                        if not isinstance(existing, list):
                            existing = []
                    except json.JSONDecodeError:
                        existing = []
                existing.append(
                    {
                        "type": "phase_graph_unresolvable",
                        "engine_iter": engine_iter,
                        "phase_ids": unresolved_phases,
                        "task_id": task_id,
                        "detected_at": now_iso(),
                        "action": "return_to_planned_for_regeneration",
                    }
                )
                warnings_file.write_text(
                    json.dumps(existing, ensure_ascii=False, indent=2)
                )
                try:
                    subprocess.run(
                        [
                            "bash",
                            str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                            "L2",
                            f"phases.json: unresolved dependency ({task_id})",
                            f"engine_iter={engine_iter} 达到 PHASE_MAX_ENGINE_ITER, "
                            f"phase {unresolved_phases} 无法解析 → 退回 planned",
                        ],
                        capture_output=True,
                        timeout=5,
                        env=_sanitized_env(),
                    )
                except Exception as e:
                    _log.warning(
                        "ccc-notify unresolvable failed for %s: %s",
                        task_id,
                        e,
                        exc_info=True,
                    )
            except OSError as e:
                _log.warning(
                    "write unresolvable phases failed for %s: %s", task_id, e
                )

    return {
        "executable": sorted(executable),
        "blocked": sorted(blocked_on_disk),
        "skipped": sorted(skipped_on_disk),
        "all_terminal": all_terminal,
        "all_failed_or_skipped": all_failed_or_skipped,
        "engine_iter": engine_iter,
        "unresolvable": unresolvable,
    }


def _read_engine_iter_meta(task_id: str) -> dict:
    """v0.27.1: 读 phases.json metadata 行的完整 engine_iter 元数据。"""
    phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
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
    except OSError as e:
        _log.warning("read engine_iter meta failed for %s: %s", task_id, e)
    return {}


def _write_engine_iter_meta(task_id: str, meta: dict) -> None:
    """v0.27.1: 把 engine_iter 元数据写入 phases.json 顶层 metadata 行。"""
    phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        return
    try:
        lines = phases_file.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as e:
        _log.warning("read phases for engine_iter meta failed %s: %s", task_id, e)
        return
    found = False
    new_lines: list[str] = []
    for line in lines:
        line_s = line.strip()
        if not line_s:
            new_lines.append(line)
            continue
        try:
            obj = json.loads(line_s)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue
        if isinstance(obj, dict) and "engine_iter" in obj:
            obj.update(meta)
            new_lines.append(json.dumps(obj, ensure_ascii=False) + "\n")
            found = True
        else:
            new_lines.append(line if line.endswith("\n") else line + "\n")
    if not found:
        new_lines.insert(0, json.dumps(meta, ensure_ascii=False) + "\n")
    try:
        _store_atomic_write(phases_file, "".join(new_lines))
    except OSError as e:
        _log.warning("write engine_iter meta failed for %s: %s", task_id, e)


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
    _write_engine_iter_meta(
        task_id,
        {
            "engine_iter": value,
            "engine_iter_phase": cur_phase,
        },
    )


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
        _log.error(
            "failure-isolation: %s all phases failed/skipped → abnormal", task_id
        )
        return True
    except Exception as exc:
        _log.error("failure-isolation: %s move to abnormal failed: %s", task_id, exc)
        return False



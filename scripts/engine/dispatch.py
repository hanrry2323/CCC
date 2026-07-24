"""engine/dispatch.py — 角色调度编排纯 helper。

方案 1.1（2026-07-24）ccc-engine.py 拆分第二阶段：

本模块承载与 phase / 调度相关的**纯函数 helper**（无副作用、独立可测）。
后续会把 _try_launch_planned 等大块编排逻辑渐进搬入。

本批（commit 1.1.1）只搬纯 helper：
- _phase_market_subid: per-phase marker subid（双下划线隔离 task/phase）
- _top_level_roots: distinct top-level path prefixes（跳过 .ccc hygiene）
- _phase_to_pgroup: phase→OpenCode pool/marker id（p1/p2/…）
- _wall_seconds_from_started: active_tasks started_at → wall seconds

未搬（强耦合，需后续独立 commit）：
- _try_launch_planned (ccc-engine.py:1850-2114, 264 行)
- _try_launch_planned_parallel (ccc-engine.py:2147-2189, 42 行)
- _build_phase_prompt / _launch_parallel_phase / _check_parallel_phase_done
- _force_serial_multi_root / _group_parallel_phases

Why not 一次拆完：ccc-engine.py 主循环 + launch + result 块是强耦合核心，
搬动需大量参数注入 + 回调改造，工程浩大且引入新 bug 风险。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _phase_market_subid(tid: str, phase_num: int) -> str:
    """Per-phase marker subid，避免并行 phase 写在同 task_id.{done,pid,exitcode}。

    用「task_id__p{N}」双下划线，与 ccc-board 的「task_id-p{N}」区分。
    """
    return f"{tid}__p{phase_num}"


def _top_level_roots(paths: list[str]) -> set[str]:
    """Distinct top-level path prefixes (skip .ccc hygiene)."""
    roots: set[str] = set()
    for raw in paths:
        s = str(raw or "").strip().lstrip("./")
        if not s or s.startswith(".ccc"):
            continue
        part = Path(s).parts[0] if Path(s).parts else ""
        if part:
            roots.add(part)
    return roots


def _phase_to_pgroup(p: int) -> str:
    """OpenCode pool / marker 用的 phase id（与 ccc-board 一致：task_id-pN）。"""
    # 注：当前 _try_launch_planned 调 dev_role_launch，里头 phase_id=task_id-pN。
    # 本 dispatcher 用 pgroup = task_id__pN 双下划线以隔离 task-level 标记。
    return f"p{p}"


def _wall_seconds_from_started(started_at: str | None) -> float | None:
    """Parse active_tasks started_at → wall seconds; None if unparseable."""
    if not started_at:
        return None
    try:
        s = str(started_at).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds()), 2)
    except (TypeError, ValueError, OSError):
        return None

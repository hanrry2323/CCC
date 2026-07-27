"""_role_tool.py — 角色启动前置校验（不占 retry budget）。

职责：在角色 execute/Popen 前做可恢复性检查，校验失败返回原因，
      调用方不递增 retry_count，不消耗 OpenCode 槽。

参考 pi agent-loop.ts L600-664 prepareToolCall，
      检验失败返回 kind: "immediate"，不占执行槽。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from _config import get_logger

if TYPE_CHECKING:
    from _board_store import FileBoardStore

_log = get_logger("role_tool")


def _read_phases_json(ws: Path, task_id: str) -> list[dict] | None:
    """读 phases.json，返回 phase list（含 schema 行）。"""
    pf = ws / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not pf.is_file():
        return None
    try:
        lines = pf.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    phases: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "phase" in obj:
            phases.append(obj)
    return phases


def _find_running_phase(phases: list[dict]) -> int | None:
    """找当前应执行 phase：in_progress 优先 → pending/blocked 第一个。"""
    running = [p for p in phases if p.get("status") == "in_progress"]
    if running:
        return int(running[0].get("phase", 0))
    # 退到 pending / blocked 的第一个
    candidates = [
        p
        for p in phases
        if p.get("status") in ("pending", "blocked")
    ]
    if candidates:
        return int(candidates[0].get("phase", 0))
    return None


def prepare_role_call(
    task_id: str,
    ws: Path,
    *,
    store: FileBoardStore | None = None,
) -> tuple[bool, str]:
    """角色启动前置校验。

    校验失败返回 (False, reason)。
    调用方不应计入 retry budget（不调 increment_retry_count）。

    Args:
        task_id: 任务 ID
        ws: workspace 路径
        store: 可选 FileBoardStore（用于 task 存在性检查）

    Returns:
        (ok: bool, reason: str)
    """
    # 1. task 存在性
    if store is None:
        from _board_store import FileBoardStore

        store = FileBoardStore(ws)
    _, task = store.find_task(task_id)
    if not task:
        return False, f"task '{task_id}' not found"

    # 2. phases.json 存在且当前 phase 可解析
    phases = _read_phases_json(ws, task_id)
    if not phases:
        return False, "phases.json 不存在或格式异常"
    cur = _find_running_phase(phases)
    if cur is None:
        # 所有 phase 已 done 或 failed → 不是正常启动场景
        statuses = {p.get("status", "?") for p in phases}
        return False, f"当前无待执行 phase（statuses: {', '.join(sorted(statuses))}）"

    # 3. scope 路径校验（当前 phase）
    # 目录级 scope（如 "scripts/"）跳过。
    # 缺失的 in-tree 叶文件 = 待创建（OpenCode/dev 会写）→ 放行；
    # 禁止越出 workspace 的绝对/.. 路径。
    ws_res = ws.resolve()
    for p in phases:
        if int(p.get("phase", 0)) != cur:
            continue
        scope = p.get("scope") or []
        for path_entry in scope:
            path_str = str(path_entry).strip()
            if not path_str:
                continue
            if path_str.endswith("/"):
                continue
            target = (ws / path_str).resolve()
            try:
                target.relative_to(ws_res)
            except ValueError:
                return False, f"scope 路径越界: {path_str}"
            # exists or create-new-file — both OK
        break

    # 4. pids_dir 可写
    pids_dir = ws / ".ccc" / "pids"
    try:
        pids_dir.mkdir(parents=True, exist_ok=True)
        test_file = pids_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
    except OSError as e:
        return False, f"pids_dir 不可写: {e}"

    # 5. reports_dir 可写（exec.log 落点）
    reports_dir = ws / ".ccc" / "reports"
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        test_file = reports_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
    except OSError as e:
        return False, f"reports_dir 不可写: {e}"

    return True, ""

"""board.roles.ops — extracted from ccc-board.py (behavior-preserving)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import uuid
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from _config import Config, get_logger, parse_duration
from _executor import _claude_env, _sanitized_env
from _board_store import FileBoardStore, _atomic_write as _store_atomic_write
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id
from _utils import sanitize_prompt_input as _sanitize_prompt_input
from _claude_cli import ClaudeCliMissing, resolve_claude_cli
import phase_lint

from board.context import get_workspace, set_workspace, board_dir, ccc_home
from board.lock import (
    acquire_named_lock as _acquire_product_lock,
    release_named_lock as _release_product_lock,
)
from board.prompt import build_dev_phase_prompt
from board.phase import (
    _load_phases,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _current_running_phase,
    _mark_phase_done,
    _mark_phase_failed,
    _check_phase_failures,
    _move_task_to_abnormal_if_all_terminal_failed,
)
from board.roles.common import (
    cfg,
    store,
    _log,
    CCC_HOME,
    MAX_RETRY,
    MAX_STALE_HOURS,
    sanitize_id,
    now_iso,
    _quarantine,
    list_tasks,
    move_task,
    create_task,
    update_index,
    _get_cfg,
    _get_store,
    _reset_lazy,
    _backoff_seconds,
    _load_timeout,
    _load_retry_cap,
    _load_retry_from_phases,
    _claude_bin,
    _get_relay_url,
    WORKSPACES,
)

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

    # 1. Stale 检测：全非终态列（in_progress + testing + planned）→ 异常列
    # v0.31 (P4.1): 从仅 in_progress 扩大到全非终态，堵 testing/planned 静默死状态
    from datetime import datetime as _dt

    _STALE_COLUMNS = ["in_progress", "testing", "planned"]
    now = _dt.now(timezone.utc)
    for col in _STALE_COLUMNS:
        for task in list_tasks(col):
            # v0.34 (P4): 优先用 phase_last_advanced_ts（phase 粒度）, 其次 updated_at
            updated_str = task.get("phase_last_advanced_ts", task.get("updated_at", task.get("created_at", "")))
            if not updated_str:
                continue
            try:
                updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
                hours_stale = (now - updated).total_seconds() / 3600
                if hours_stale > MAX_STALE_HOURS:
                    _quarantine(
                        task["id"],
                        f"{col} 滞留 {hours_stale:.1f}h（阈值 {MAX_STALE_HOURS}h），自动隔离",
                    )
                    health["stale_detected"] += 1
                    _log.info(
                        f"[ops] stale: {task['id']} {col} 滞留 {hours_stale:.1f}h → abnormal"
                    )
            except (ValueError, TypeError) as e:
                _log.warning(
                    "ops stale timestamp parse failed for %s: %s", task.get("id"), e
                )
    pid_dir = get_workspace() / ".ccc" / "pids"
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

    # 3. 检查 abnormal 列任务（上报 + v0.34 P6 自动归因）
    abnormal_tasks = list_tasks("abnormal")
    if abnormal_tasks:
        _log.info(f"[ops] ⚠ abnormal 列有 {len(abnormal_tasks)} 个任务需处理:")
        for t in abnormal_tasks:
            _log.info(f"  • {t['id']}: {t.get('note', '?')[:120]}")
            # v0.34 (P6.1): abnormal > 24h → 自动归因
            _ts_str = t.get("updated_at", t.get("created_at", ""))
            if _ts_str:
                try:
                    from datetime import datetime as _dt2
                    _ts = _dt2.fromisoformat(_ts_str.replace("Z", "+00:00"))
                    if (now - _ts).total_seconds() > 86400:
                        _note = t.get("note", "")
                        try:
                            from _capability_evolver import analyze_failure
                            _rca = analyze_failure(t["id"], _note)
                            if _rca:
                                _log.info(
                                    f"[ops] auto-heal: {t['id']} → {_rca.get('pattern', '?')}"
                                )
                                # 追加分析建议到 note
                                t["note"] = _note + (
                                    f"\n[自动归因] pattern={_rca.get('pattern', '?')}"
                                    f"\n建议: {_rca.get('fix', '需人工')}"
                                )
                                # 原地重写 abnormal 列 task
                                _tp = get_workspace() / ".ccc" / "board" / "abnormal" / f"{t['id']}.jsonl"
                                if _tp.exists():
                                    _tp.write_text(
                                        json.dumps(t, ensure_ascii=False) + "\n"
                                    )
                                health["auto_healed"] = health.get("auto_healed", 0) + 1
                        except ImportError:
                            pass
                except (ValueError, TypeError):
                    pass
        health["abnormal_count"] = len(abnormal_tasks)

    # 4. git ahead check
    import subprocess as sp

    try:
        from _workspace_registry import list_registered_entries

        _git_roots = [Path(e["path"]) for e in list_registered_entries()]
    except Exception:
        _git_roots = [get_workspace()]
    for proj in _git_roots:
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

    # 6. v0.34 (P6.3): 看板自平衡 — backlog 空 → audit 自动补；planned 堆积 > 5 → 限流
    _backlog_count = len(list_tasks("backlog"))
    _planned_count = len(list_tasks("planned"))
    if _backlog_count == 0:
        _log.info("[ops] backlog 空，自动触发 audit 补充")
        try:
            from _audit import run_audit
            run_audit(get_workspace())
            health["audit_refill"] = 1
        except ImportError:
            pass
    if _planned_count > 5:
        _log.info(f"[ops] planned 堆积（{_planned_count}），报告不阻塞")
        health["planned_pileup"] = _planned_count
    health["backlog_count"] = _backlog_count
    health["planned_count"] = _planned_count

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
    pid_dir = get_workspace() / ".ccc" / "pids"
    metrics = {
        "updated_at": now_iso(),
        "tasks_in_flight": len(list_tasks("in_progress")) + len(list_tasks("testing")),
        "abnormal_count": len(list_tasks("abnormal")),
        "pids_count": len(list(pid_dir.glob("*.pid"))) if pid_dir.exists() else 0,
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob("*-L*.md"))),
        "launchd_missing": health["launchd_missing"],
    }
    metrics_file = get_workspace() / ".ccc" / "metrics.json"
    metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")

    return {"role": "ops", "health": health}


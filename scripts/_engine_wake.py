"""_engine_wake.py — 下任务 / 日审建卡 → 强制 enabled + 唤醒 Engine（v0.41）

产品规则：用户下达任务 = 自动化开工信号，无确认弹窗。
不打开 invent（禁止自造）；已是 invent 则保持。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_log = logging.getLogger("ccc.engine_wake")

WAKE_FILE = Path.home() / ".ccc" / "engine.wake"
CCC_HOME = Path(os.environ.get("CCC_HOME") or Path(__file__).resolve().parent.parent)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_wake(*, reason: str, task_id: str | None = None) -> Path:
    WAKE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": _now_iso(),
        "reason": reason,
        "task_id": task_id,
    }
    WAKE_FILE.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return WAKE_FILE


def consume_wake() -> Optional[dict[str, Any]]:
    """若存在 wake 文件则读取并删除，返回 payload。"""
    if not WAKE_FILE.is_file():
        return None
    try:
        data = json.loads(WAKE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {"reason": "wake"}
    try:
        WAKE_FILE.unlink()
    except OSError:
        pass
    return data if isinstance(data, dict) else {"reason": "wake"}


def _bootstrap_engine_launchd() -> tuple[bool, str]:
    """尝试 launchctl 拉起 com.ccc.engine。失败不抛（前台/无 plist 环境）。"""
    uid = os.getuid()
    label = f"gui/{uid}/com.ccc.engine"
    dst = Path.home() / "Library" / "LaunchAgents" / "com.ccc.engine.plist"
    src = Path.home() / "Library" / "LaunchAgents" / "disabled-ccc" / "com.ccc.engine.plist"
    notes: list[str] = []
    try:
        if src.is_file() and not dst.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            notes.append("restored_plist")
        subprocess.run(
            ["launchctl", "enable", label],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if dst.is_file():
            r = subprocess.run(
                ["launchctl", "bootstrap", f"gui/{uid}", str(dst)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if r.returncode != 0:
                subprocess.run(
                    ["launchctl", "load", "-w", str(dst)],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                notes.append("load_fallback")
            else:
                notes.append("bootstrap_ok")
            return True, ",".join(notes) or "started"
        notes.append("no_plist")
        return False, "no_engine_plist"
    except Exception as exc:
        _log.warning("bootstrap engine failed: %s", exc)
        return False, str(exc)[:200]


def ensure_engine_for_task(
    *,
    reason: str = "task_dispatch",
    task_id: str | None = None,
    start_launchd: bool = True,
    workspace: Path | str | None = None,
    workspace_name: str | None = None,
) -> dict[str, Any]:
    """下任务后调用：非 invent → enabled；登记 workspace；写 wake；可选 bootstrap launchd。

    source=task_dispatch 表示用户显式下达（非 agent 自启用）。
    workspace: 若提供，幂等写入 ~/.ccc/workspaces.json，供 Engine 发现非 CCC 项目。
    """
    from _ccc_control import get_mode, set_mode

    mode_before = get_mode()
    mode_after = mode_before
    control_changed = False

    if mode_before == "invent":
        pass  # 保持 invent
    elif mode_before != "enabled":
        set_mode(
            "enabled",
            reason=f"{reason}" + (f":{task_id}" if task_id else ""),
            source="task_dispatch",
        )
        mode_after = "enabled"
        control_changed = True

    workspace_reg = None
    if workspace:
        try:
            from _workspace_registry import register_workspace

            workspace_reg = register_workspace(
                workspace, name=workspace_name
            )
        except Exception as exc:
            workspace_reg = {"ok": False, "error": str(exc)[:200]}

    wake_path = write_wake(reason=reason, task_id=task_id)
    launched = False
    launch_note = "skipped"
    if start_launchd:
        launched, launch_note = _bootstrap_engine_launchd()

    result = {
        "ok": True,
        "mode_before": mode_before,
        "mode_after": mode_after,
        "control_changed": control_changed,
        "wake_file": str(wake_path),
        "launchd": launched,
        "launch_note": launch_note,
        "task_id": task_id,
        "reason": reason,
        "workspace_reg": workspace_reg,
    }
    _log.info("ensure_engine_for_task %s", result)
    return result

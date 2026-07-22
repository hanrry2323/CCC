"""_engine_wake.py — 下任务 / 日审建卡 → 强制 enabled + 唤醒 Engine（v0.41+）

产品规则：用户下达任务 = 自动化开工信号，无确认弹窗。
禁止 invent / 自造；存量 invent 一律降级 enabled。
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


def write_wake(
    *,
    reason: str,
    task_id: str | None = None,
    workspace: Path | str | None = None,
) -> Path:
    WAKE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "ts": _now_iso(),
        "reason": reason,
        "task_id": task_id,
    }
    if workspace:
        try:
            payload["workspace"] = str(Path(workspace).resolve())
        except OSError:
            payload["workspace"] = str(workspace)
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


def _kickstart_engine_launchd() -> tuple[bool, str]:
    """对已 load 的 com.ccc.engine 做 kickstart -k（bootstrap 不够时必用）。"""
    uid = os.getuid()
    label = f"gui/{uid}/com.ccc.engine"
    try:
        r = subprocess.run(
            ["launchctl", "kickstart", "-k", label],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if r.returncode == 0:
            return True, "kickstart_ok"
        err = (r.stderr or r.stdout or "").strip()[:120]
        return False, f"kickstart_fail:{err or r.returncode}"
    except Exception as exc:
        _log.warning("kickstart engine failed: %s", exc)
        return False, str(exc)[:200]


def _bootstrap_engine_launchd() -> tuple[bool, str]:
    """尝试 launchctl 拉起 com.ccc.engine。失败不抛（前台/无 plist 环境）。

    bootstrap/load 只保证 job 在 launchd 里；若已 load 但 stopped，必须再 kickstart。
    """
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
        if not dst.is_file():
            notes.append("no_plist")
            return False, "no_engine_plist"
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
        # Already-loaded + stopped (e.g. watchdog exit 78) needs kickstart
        if not is_engine_running():
            kicked, kick_note = _kickstart_engine_launchd()
            notes.append(kick_note)
            if not kicked and is_engine_running():
                pass  # race: process came up
            return kicked or is_engine_running(), ",".join(notes)
        notes.append("already_running")
        return True, ",".join(notes) or "started"
    except Exception as exc:
        _log.warning("bootstrap engine failed: %s", exc)
        return False, str(exc)[:200]


def is_engine_running() -> bool:
    """检测 ccc-engine 进程是否在跑（pgrep 或 launchctl）。"""
    try:
        r = subprocess.run(
            ["pgrep", "-f", "ccc-engine.py"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0:
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["launchctl", "list", "com.ccc.engine"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode != 0 or not r.stdout:
            return False
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 1 and parts[0].isdigit() and int(parts[0]) > 0:
                return True
        import re

        m = re.search(r'"PID"\s*=\s*(\d+)', r.stdout)
        return bool(m and int(m.group(1)) > 0)
    except Exception:
        return False


def _stop_engine_launchd() -> tuple[bool, str]:
    """停掉 com.ccc.engine（bootout），plist 挪到 disabled-ccc。"""
    uid = os.getuid()
    label = f"gui/{uid}/com.ccc.engine"
    dst = Path.home() / "Library" / "LaunchAgents" / "com.ccc.engine.plist"
    park = Path.home() / "Library" / "LaunchAgents" / "disabled-ccc"
    notes: list[str] = []
    try:
        subprocess.run(
            ["launchctl", "bootout", label],
            capture_output=True,
            timeout=15,
            check=False,
        )
        notes.append("bootout")
        subprocess.run(
            ["launchctl", "unload", "-w", str(dst)],
            capture_output=True,
            timeout=15,
            check=False,
        )
        if dst.is_file():
            park.mkdir(parents=True, exist_ok=True)
            target = park / "com.ccc.engine.plist"
            try:
                if target.exists():
                    target.unlink()
                dst.rename(target)
                notes.append("parked_plist")
            except OSError as exc:
                notes.append(f"park_fail:{exc}")
        return True, ",".join(notes)
    except Exception as exc:
        _log.warning("stop engine failed: %s", exc)
        return False, str(exc)[:200]


def stop_engine(*, reason: str = "hub_manual_stop", source: str = "hub") -> dict[str, Any]:
    """Hub 手动停 Engine：控制面 → ui，并 bootout launchd。"""
    from _ccc_control import get_mode, set_mode

    mode_before = get_mode()
    set_mode("ui", reason=reason, source=source)
    ok, note = _stop_engine_launchd()
    # 给进程一点时间退出
    import time

    time.sleep(0.4)
    return {
        "ok": ok,
        "action": "stop",
        "mode_before": mode_before,
        "mode_after": "ui",
        "launch_note": note,
        "engine_running": is_engine_running(),
    }


def start_engine(*, reason: str = "hub_manual_start", source: str = "hub") -> dict[str, Any]:
    """Hub 手动启 Engine：enabled + bootstrap。"""
    return ensure_engine_for_task(
        reason=reason,
        task_id="hub-manual",
        start_launchd=True,
    ) | {"action": "start", "engine_running": is_engine_running()}


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

    # v0.42.4: invent 永久禁用 — 任何残留 invent 都降为 enabled
    if mode_before == "invent" or mode_before != "enabled":
        if mode_before != "enabled":
            set_mode(
                "enabled",
                reason=f"{reason}" + (f":{task_id}" if task_id else ""),
                source="task_dispatch" if source_is_dispatch(reason) else "hub",
            )
            mode_after = "enabled"
            control_changed = True

    workspace_reg = None
    if workspace:
        try:
            from _workspace_registry import (
                ROLE_ORCH,
                is_orch_path,
                register_workspace,
            )

            # v0.51: CCC / orch always registered engine=false (never Engine-consumable)
            force_orch = is_orch_path(workspace) or (
                workspace_name
                and str(workspace_name).strip().upper() in ("CCC",)
            )
            workspace_reg = register_workspace(
                workspace,
                name=workspace_name,
                role=ROLE_ORCH if force_orch else None,
                engine=False if force_orch else None,
            )
        except Exception as exc:
            workspace_reg = {"ok": False, "error": str(exc)[:200]}

    wake_path = write_wake(reason=reason, task_id=task_id, workspace=workspace)
    launched = False
    launch_note = "skipped"
    if start_launchd:
        launched, launch_note = _bootstrap_engine_launchd()
        # Double-check: bootstrap may report ok while process still dead
        if not is_engine_running():
            kicked, kick_note = _kickstart_engine_launchd()
            launch_note = f"{launch_note},{kick_note}"
            launched = kicked or launched

    running = is_engine_running()
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
        "engine_running": running,
        # Desktop toast: distinguish "queued but Engine dead" vs truly awake
        "message": (
            None
            if running
            else f"queued; Engine not running ({launch_note})"
        ),
    }
    _log.info("ensure_engine_for_task %s", result)
    return result


def source_is_dispatch(reason: str) -> bool:
    return not str(reason or "").startswith("hub_manual")

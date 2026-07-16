"""_ccc_control.py — CCC 运行控制面（v0.40）

业务状态机（SSOT: ~/.ccc/control.json）：

  disabled  → 默认。禁止 Engine / 禁止 launchd 常驻 Hub·Board
  ui        → 仅允许 Hub(:7777) + Board API(:7775)；禁止 Engine
  enabled   → Engine 只消费已有队列（禁止 invent / abnormal 回灌）
  invent    → Engine + 允许自造任务（audit→backlog / evolve / auto_replenish / abnormal 重试）

前端开发请用前台脚本（不改 control、不装 launchd）：
  bash scripts/ccc-hub-dev.sh

红线 12：禁止 agent 自主 enable / invent / ui。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Mode = Literal["disabled", "ui", "enabled", "invent"]

CONTROL_DIR = Path.home() / ".ccc"
CONTROL_FILE = CONTROL_DIR / "control.json"
DISABLED_SENTINEL = CONTROL_DIR / "DISABLED"

VALID_MODES = frozenset({"disabled", "ui", "enabled", "invent"})
ENGINE_MODES = frozenset({"enabled", "invent"})
UI_MODES = frozenset({"ui", "enabled", "invent"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_raw() -> dict[str, Any]:
    if CONTROL_FILE.is_file():
        try:
            data = json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _write_raw(data: dict[str, Any]) -> None:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONTROL_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(CONTROL_FILE)


def get_mode() -> Mode:
    """返回当前模式。安全默认：disabled。"""
    if DISABLED_SENTINEL.is_file():
        return "disabled"
    data = _read_raw()
    mode = data.get("mode")
    if mode in VALID_MODES:
        return mode  # type: ignore[return-type]
    return "disabled"


def is_enabled() -> bool:
    """队列消费模式（不含 invent）。"""
    return get_mode() == "enabled"


def is_invent_mode() -> bool:
    return get_mode() == "invent"


def is_ui_mode() -> bool:
    return get_mode() == "ui"


def is_disabled() -> bool:
    return get_mode() == "disabled"


def may_start_engine() -> bool:
    """是否允许启动 Engine（enabled 或 invent）。"""
    return get_mode() in ENGINE_MODES


def may_invent() -> bool:
    """是否允许自造任务 / abnormal 自动回灌。仅 invent。"""
    return get_mode() == "invent"


def may_start_ui() -> bool:
    """是否允许 launchd 常驻 Hub/Board。"""
    return get_mode() in UI_MODES


def foreground_bypass() -> bool:
    """前台开发入口：CCC_FOREGROUND=1 时跳过控制面拒启（仍不启 Engine）。"""
    return os.environ.get("CCC_FOREGROUND", "").strip() in ("1", "true", "yes")


def set_mode(mode: Mode, *, reason: str = "", source: str = "cli") -> dict[str, Any]:
    """写入控制面。返回新状态 dict。"""
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")
    reasons = {
        "disabled": "user disable",
        "ui": "user ui-only",
        "enabled": "user enable (queue consumer)",
        "invent": "user invent (may create work)",
    }
    data = {
        "schema_version": "1.2",
        "mode": mode,
        "updated_at": _now_iso(),
        "reason": reason or reasons[mode],
        "source": source,
        "policy": {
            "start_paths": (
                ["launchd:com.ccc.engine"] if mode in ENGINE_MODES else []
            ),
            "ui_paths": ["launchd:com.ccc.chat-server", "launchd:com.ccc.board"],
            "forbid_popen_engine": True,
            "forbid_crontab_autostart": True,
            "empty_board_idle": True,
            "auto_replenish_default": False,
            "queue_consumer_only": mode == "enabled",
            "invent_allowed": mode == "invent",
            "frontend_dev": "bash scripts/ccc-hub-dev.sh",
        },
    }
    _write_raw(data)
    if mode == "disabled":
        DISABLED_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
        DISABLED_SENTINEL.write_text(
            f"# CCC disabled {_now_iso()}\n"
            f"# SSOT: {CONTROL_FILE}\n"
            f"# frontend: bash scripts/ccc-hub-dev.sh\n"
            f"# ui only:  bash scripts/ccc-autostart-guard.sh ui [--start]\n"
            f"# queue:    bash scripts/ccc-autostart-guard.sh enable [--start]\n"
            f"# invent:   bash scripts/ccc-autostart-guard.sh invent [--start]\n",
            encoding="utf-8",
        )
    else:
        try:
            DISABLED_SENTINEL.unlink()
        except OSError:
            pass
    return data


def status_dict() -> dict[str, Any]:
    data = _read_raw()
    mode = get_mode()
    return {
        "mode": mode,
        "enabled": mode == "enabled",
        "invent": mode == "invent",
        "ui_allowed": mode in UI_MODES,
        "engine_allowed": mode in ENGINE_MODES,
        "invent_allowed": mode == "invent",
        "control_file": str(CONTROL_FILE),
        "disabled_sentinel": DISABLED_SENTINEL.is_file(),
        "updated_at": data.get("updated_at"),
        "reason": data.get("reason"),
        "policy": data.get("policy")
        or {
            "forbid_popen_engine": True,
            "forbid_crontab_autostart": True,
            "frontend_dev": "bash scripts/ccc-hub-dev.sh",
        },
    }


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(argv if argv is not None else sys.argv[1:])
    cmd = args[0] if args else "status"
    if cmd == "status":
        print(json.dumps(status_dict(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "enable":
        reason = " ".join(args[1:]) if len(args) > 1 else "cli enable"
        print(json.dumps(set_mode("enabled", reason=reason, source="cli"), indent=2))
        return 0
    if cmd == "invent":
        reason = " ".join(args[1:]) if len(args) > 1 else "cli invent"
        print(json.dumps(set_mode("invent", reason=reason, source="cli"), indent=2))
        return 0
    if cmd == "ui":
        reason = " ".join(args[1:]) if len(args) > 1 else "cli ui"
        print(json.dumps(set_mode("ui", reason=reason, source="cli"), indent=2))
        return 0
    if cmd == "disable":
        reason = " ".join(args[1:]) if len(args) > 1 else "cli disable"
        print(json.dumps(set_mode("disabled", reason=reason, source="cli"), indent=2))
        return 0
    print(
        "usage: _ccc_control.py {status|disable|ui|enable|invent} [reason]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

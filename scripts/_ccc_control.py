"""_ccc_control.py — CCC 运行控制面（v0.39）

业务状态机（SSOT: ~/.ccc/control.json）：

  disabled  → 任何路径禁止拉起 Engine / opencode / 旁路 python&
  enabled   → 允许；仅允许经 launchd com.ccc.engine 单点拉起
              （patrol 不得 Popen；loop-monitor 不得自启）

兼容：
  - 存在 ~/.ccc/DISABLED 文件 → 视为 disabled（旧哨兵）
  - 无 control.json 且无 DISABLED → 默认 disabled（生产力安全默认）
    显式 enable 后才进入 enabled

红线对齐：红线 12「禁止 agent 自主启用」→ 代码层禁止旁路自启。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Mode = Literal["disabled", "enabled"]

CONTROL_DIR = Path.home() / ".ccc"
CONTROL_FILE = CONTROL_DIR / "control.json"
DISABLED_SENTINEL = CONTROL_DIR / "DISABLED"

VALID_MODES = frozenset({"disabled", "enabled"})


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
    # 旧哨兵优先（disable 脚本可能只写了它）
    if DISABLED_SENTINEL.is_file():
        return "disabled"
    data = _read_raw()
    mode = data.get("mode")
    if mode in VALID_MODES:
        return mode  # type: ignore[return-value]
    # 无配置 → 默认 disabled（不自动干活）
    return "disabled"


def is_enabled() -> bool:
    return get_mode() == "enabled"


def is_disabled() -> bool:
    return get_mode() == "disabled"


def may_start_engine() -> bool:
    """是否允许任何路径尝试启动 Engine。"""
    return is_enabled()


def set_mode(mode: Mode, *, reason: str = "", source: str = "cli") -> dict[str, Any]:
    """写入控制面。返回新状态 dict。"""
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")
    data = {
        "schema_version": "1.0",
        "mode": mode,
        "updated_at": _now_iso(),
        "reason": reason or ("user enable" if mode == "enabled" else "user disable"),
        "source": source,
        "policy": {
            "start_paths": ["launchd:com.ccc.engine"],
            "forbid_popen_engine": True,
            "forbid_crontab_autostart": True,
            "empty_board_idle": True,
            "auto_replenish_default": False,
        },
    }
    _write_raw(data)
    if mode == "disabled":
        DISABLED_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
        DISABLED_SENTINEL.write_text(
            f"# CCC disabled {_now_iso()}\n"
            f"# SSOT: {CONTROL_FILE}\n"
            f"# enable: python3 scripts/_ccc_control.py enable\n"
            f"#     or: bash scripts/ccc-autostart-guard.sh enable\n",
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
        "control_file": str(CONTROL_FILE),
        "disabled_sentinel": DISABLED_SENTINEL.is_file(),
        "updated_at": data.get("updated_at"),
        "reason": data.get("reason"),
        "policy": data.get("policy")
        or {
            "start_paths": ["launchd:com.ccc.engine"],
            "forbid_popen_engine": True,
            "forbid_crontab_autostart": True,
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
    if cmd == "disable":
        reason = " ".join(args[1:]) if len(args) > 1 else "cli disable"
        print(json.dumps(set_mode("disabled", reason=reason, source="cli"), indent=2))
        return 0
    print("usage: _ccc_control.py {status|enable|disable} [reason]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""_ccc_control.py — CCC 运行控制面（v0.42.4）

业务状态机（SSOT: ~/.ccc/control.json）：

  disabled  → 默认。禁止 Engine / 禁止 launchd 常驻 Hub·Board
  ui        → 仅允许 Hub(:7777) + Board API(:7775)；禁止 Engine
  enabled   → Engine 只消费**用户显式下达**的队列（禁止一切自造/自动投入）
  invent    → **已永久禁用**（v0.42.4）：set_mode("invent") 强制降级为 enabled

前端开发请用前台脚本（不改 control、不装 launchd）：
  bash scripts/ccc-hub-dev.sh

红线 12：禁止 agent 自主 enable / invent / ui。
例外：source=task_dispatch / daily_review — 用户下达任务或日审建卡，强制 enabled+wake（产品规则）。

v0.42.4 内存红线：永久禁止「自动识别任务投入」——
  audit→backlog / evolve→backlog / auto_replenish / abnormal 自动回灌 / invent 模式。
  仅用户在 Hub/Board 显式建卡或定稿转任务，才允许入队。
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

Mode = Literal["disabled", "ui", "enabled", "invent"]

CONTROL_DIR = Path.home() / ".ccc"
CONTROL_FILE = CONTROL_DIR / "control.json"
DISABLED_SENTINEL = CONTROL_DIR / "DISABLED"

VALID_MODES = frozenset({"disabled", "ui", "enabled", "invent"})
ENGINE_MODES = frozenset({"enabled", "invent"})  # invent 仅兼容旧 control.json 读路径
UI_MODES = frozenset({"ui", "enabled", "invent"})

# set_mode source 白名单（红线 12 实质化）
# - cli:         命令行 / 主入口（默认）
# - hub:         Hub 后端（Basic Auth 已认证的用户操作）
# - task_dispatch: 用户显式下达任务（CCC 协议允许）
# - daily_review: 日审建卡
# - ops_manual:  运维手动
# 其它 source 一律 ValueError（修复 audit-2026-07-24 类别⑤）
ALLOWED_SET_MODE_SOURCES = frozenset(
    {"cli", "hub", "task_dispatch", "daily_review", "ops_manual"}
)

# 永久关闭：自动识别 / 自造任务投入（audit/evolve/replenish/abnormal 回灌）
INVENT_HARD_DISABLED = True


def _now_iso() -> str:
    from _utils import now_iso_utc

    return now_iso_utc()


def _read_raw() -> dict[str, Any]:
    """共享锁读取 control.json。损坏 JSON 静默回退 {}（与历史一致）。

    注意：flock 是 advisory lock；外部绕过者（Patrol / Ops / 协议允许的直写）
    不会阻塞。CCC 协议已要求外部走 CLI / API（详见 references/board-task-schema.md）。
    """
    if not CONTROL_FILE.is_file():
        return {}
    try:
        fd = os.open(str(CONTROL_FILE), os.O_RDONLY)
    except OSError:
        return {}
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
        except OSError:
            # flock 不支持时降级（仍允许读，不阻塞）
            pass
        try:
            # control.json < 1MB；read 1MB 足够
            data = json.loads(os.read(fd, 1 << 20).decode("utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    return {}


def _write_raw(data: dict[str, Any]) -> None:
    """原子写 control.json：mkstemp + fsync + dir fsync + flock(LOCK_EX)。

    修复 stability-audit-2026-07-24 类别①：固定 .tmp 名的并发覆盖 + 缺 fsync。
    """
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(CONTROL_DIR), prefix=".control-", suffix=".tmp"
    )
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError:
            pass
        content = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        os.write(fd, content)
        os.fsync(fd)
        # 目录 fsync：POSIX 持久性前提（断电后目录项仍可见）
        try:
            dir_fd = os.open(str(CONTROL_DIR), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            # macOS / Linux 通常 OK；其它平台 fsync 失败不阻塞主流程
            pass
        os.replace(tmp_name, str(CONTROL_FILE))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _emit_control_event(data: dict[str, Any]) -> None:
    """emit control_mode_change 事件到 ~/.ccc/stats/control-events.jsonl。

    修复 stability-audit-2026-07-24 类别②：事件流补全 control mode change
    （之前缺，统一事件不可见，红线 12 实质化后无审计轨迹）。
    失败不阻塞 — control.json 已写盘即可，事件流至多丢一条。
    """
    import logging

    event = {
        "ts": _now_iso(),
        "kind": "control_mode_change",
        "mode": data.get("mode"),
        "source": data.get("source"),
        "reason": data.get("reason"),
        "coerced_from": data.get("coerced_from"),
        "pid": os.getpid(),
    }
    path = Path.home() / ".ccc" / "stats" / "control-events.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        logging.getLogger("ccc").warning(
            "[control] event emit failed for %s: %s", path, exc
        )


def get_mode() -> Mode:
    """返回当前模式。安全默认：disabled。

    存量 control.json 若仍为 invent，对外仍报 invent（兼容），但 may_invent()=False。
    """
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
    """兼容旧调用：硬禁后恒 False（即使 control.json 残留 invent）。"""
    return False if INVENT_HARD_DISABLED else get_mode() == "invent"


def is_ui_mode() -> bool:
    return get_mode() == "ui"


def is_disabled() -> bool:
    return get_mode() == "disabled"


def may_start_engine() -> bool:
    """是否允许启动 Engine（enabled；invent 残留也允许跑，但不自造）。"""
    mode = get_mode()
    if mode == "enabled":
        return True
    if mode == "invent":
        # 硬禁自造后仍允许消费队列，避免旧 invent 配置把 Engine 卡死
        return True
    return False


def may_invent() -> bool:
    """是否允许自造 / 自动识别投入任务。v0.42.4 起永久 False。"""
    if INVENT_HARD_DISABLED:
        return False
    return get_mode() == "invent"


def may_auto_inject_tasks() -> bool:
    """自动识别并投入 backlog 的总闸（audit/evolve/replenish）。恒 False。"""
    return False


def may_start_ui() -> bool:
    """是否允许 launchd 常驻 Hub/Board。"""
    return get_mode() in UI_MODES


def foreground_bypass() -> bool:
    """前台开发入口：CCC_FOREGROUND=1 时跳过控制面拒启（仍不启 Engine）。"""
    return os.environ.get("CCC_FOREGROUND", "").strip() in ("1", "true", "yes")


def set_mode(mode: Mode, *, reason: str = "", source: str = "cli") -> dict[str, Any]:
    """写入控制面。返回新状态 dict。

    invent 在硬禁下强制降级为 enabled（禁止自造，仍可消费用户任务）。
    source 必须在 ALLOWED_SET_MODE_SOURCES 白名单内（红线 12 实质化）。
    """
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")
    if source not in ALLOWED_SET_MODE_SOURCES:
        raise ValueError(
            f"invalid source: {source!r} (allowed: {sorted(ALLOWED_SET_MODE_SOURCES)})"
        )

    coerced = False
    if INVENT_HARD_DISABLED and mode == "invent":
        mode = "enabled"
        coerced = True
        reason = (reason or "invent refused") + " → enabled (INVENT_HARD_DISABLED)"

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
                ["launchd:com.ccc.engine"] if mode in ("enabled", "invent") else []
            ),
            "ui_paths": ["launchd:com.ccc.chat-server", "launchd:com.ccc.board"],
            "forbid_popen_engine": True,
            "forbid_crontab_autostart": True,
            "empty_board_idle": True,
            "auto_replenish_default": False,
            "queue_consumer_only": True,
            "invent_allowed": False,
            "invent_hard_disabled": INVENT_HARD_DISABLED,
            "auto_inject_tasks": False,
            "frontend_dev": "bash scripts/ccc-hub-dev.sh",
        },
    }
    if coerced:
        data["coerced_from"] = "invent"
    _write_raw(data)
    _emit_control_event(data)
    if mode == "disabled":
        DISABLED_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
        import tempfile

        text = (
            f"# CCC disabled {_now_iso()}\n"
            f"# SSOT: {CONTROL_FILE}\n"
            f"# frontend: bash scripts/ccc-hub-dev.sh\n"
            f"# ui only:  bash scripts/ccc-autostart-guard.sh ui [--start]\n"
            f"# queue:    bash scripts/ccc-autostart-guard.sh enable [--start]\n"
            f"# invent:   DISABLED permanently (v0.42.4 memory red-line)\n"
        )
        fd, tmp_name = tempfile.mkstemp(
            dir=str(DISABLED_SENTINEL.parent), prefix=".disabled-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tf:
                tf.write(text)
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(tmp_name, str(DISABLED_SENTINEL))
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
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
        "invent": False,
        "ui_allowed": mode in UI_MODES,
        "engine_allowed": may_start_engine(),
        "invent_allowed": False,
        "invent_hard_disabled": INVENT_HARD_DISABLED,
        "auto_inject_tasks": False,
        "control_file": str(CONTROL_FILE),
        "disabled_sentinel": DISABLED_SENTINEL.is_file(),
        "updated_at": data.get("updated_at"),
        "reason": data.get("reason"),
        "policy": data.get("policy")
        or {
            "forbid_popen_engine": True,
            "forbid_crontab_autostart": True,
            "invent_allowed": False,
            "auto_inject_tasks": False,
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
        # 硬禁：降级 enabled，exit 2 提示调用方
        out = set_mode("invent", reason=reason, source="cli")
        print(json.dumps(out, indent=2))
        print(
            "INVENT permanently disabled (v0.42.4); coerced to enabled",
            file=sys.stderr,
        )
        return 2
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

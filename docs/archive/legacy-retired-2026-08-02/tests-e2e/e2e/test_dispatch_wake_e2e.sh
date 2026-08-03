#!/usr/bin/env bash
# test_dispatch_wake_e2e.sh — POST 建卡 → ensure_engine_for_task 等价路径（无真实 launchd）
# 断言：control→enabled + wake 文件存在 + engine_wake 字段
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"

HOME_TMP=$(mktemp -d)
WORKSPACE=$(mktemp -d)
trap 'rm -rf "$HOME_TMP" "$WORKSPACE"' EXIT

export HOME="$HOME_TMP"
mkdir -p "$HOME/.ccc"
mkdir -p "$WORKSPACE/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
mkdir -p "$WORKSPACE/.ccc/"{plans,phases,pids,stats}

# 隔离 control / wake
python3 - <<PY
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "scripts")
import _ccc_control as ctrl
import _engine_wake as wake
from _board_store import FileBoardStore

home = Path("$HOME_TMP")
ws = Path("$WORKSPACE")
ctrl.CONTROL_DIR = home / ".ccc"
ctrl.CONTROL_FILE = ctrl.CONTROL_DIR / "control.json"
ctrl.DISABLED_SENTINEL = ctrl.CONTROL_DIR / "DISABLED"
wake.WAKE_FILE = home / ".ccc" / "engine.wake"

ctrl.set_mode("disabled", reason="e2e", source="test")
assert ctrl.get_mode() == "disabled"

store = FileBoardStore(ws)
tid = "e2e-dispatch-wake"
ok = store.create_task(
    {
        "id": tid,
        "title": "dispatch wake e2e",
        "description": "assert wake",
        "status": "backlog",
        "created_at": "2026-07-17",
        "updated_at": "2026-07-17",
    },
    column="backlog",
)
assert ok, "create_task failed"

with patch.object(wake, "_bootstrap_engine_launchd", return_value=(False, "skip")):
    engine_wake = wake.ensure_engine_for_task(
        reason="task_dispatch", task_id=tid, start_launchd=True
    )

assert engine_wake.get("ok") is True, engine_wake
assert engine_wake.get("mode_after") == "enabled", engine_wake
assert wake.WAKE_FILE.is_file(), "wake file missing"
payload = json.loads(wake.WAKE_FILE.read_text())
assert payload.get("task_id") == tid, payload
assert payload.get("reason") == "task_dispatch", payload

# 模拟 Board API 响应形状
api_shape = {"ok": True, "task_id": tid, "engine_wake": engine_wake}
assert "engine_wake" in api_shape
assert api_shape["engine_wake"]["mode_after"] == "enabled"

print("PASS dispatch-wake e2e")
print(json.dumps(api_shape, ensure_ascii=False, indent=2))
PY

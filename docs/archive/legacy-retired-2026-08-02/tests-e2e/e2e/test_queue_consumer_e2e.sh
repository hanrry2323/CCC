#!/usr/bin/env bash
# test_queue_consumer_e2e.sh — 受控路径：enabled 不 invent + failures 账本
# 不启动真实 LLM / KeepAlive。验证架构契约。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP"
mkdir -p "$TMP/.ccc"

python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import _ccc_control as ctrl
import _failure_ledger as fl

# isolate control under tmp HOME
ctrl.CONTROL_DIR = Path.home() / ".ccc"
ctrl.CONTROL_FILE = ctrl.CONTROL_DIR / "control.json"
ctrl.DISABLED_SENTINEL = ctrl.CONTROL_DIR / "DISABLED"

ctrl.set_mode("enabled", reason="e2e")
assert ctrl.may_start_engine() and not ctrl.may_invent(), "enabled must not invent"

ws = Path(".").resolve()
# simulate quarantine ledger write
fl.record_failure(
    ws,
    task_id="e2e-queue-consumer",
    role="reviewer",
    reason="structured fallback: mock claude rc=1",
    phase=1,
    from_col="testing",
    exit_code=1,
)
rows = fl.read_failures(ws, last=1)
assert rows and rows[-1]["task_id"] == "e2e-queue-consumer"
assert rows[-1]["role"] == "reviewer"
print("PASS ledger + invent gate")

ctrl.set_mode("invent", reason="e2e")
assert ctrl.may_invent()
ctrl.set_mode("disabled", reason="e2e cleanup")
print("PASS invent toggle")
PY

# template fallback
python3 - <<'PY'
import importlib.util
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from board.context import set_workspace

spec = importlib.util.spec_from_file_location(
    "ccc_board", Path("scripts/ccc-board.py").resolve()
)
ccc_board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccc_board)

fake = Path("/tmp/ccc-e2e-ws-no-tpl")
(fake / ".ccc").mkdir(parents=True, exist_ok=True)
set_workspace(fake)
text = ccc_board._load_plan_template()
assert len(text) > 50
print("PASS template fallback")
PY

echo "=== queue-consumer e2e OK ==="

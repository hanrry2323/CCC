#!/usr/bin/env bash
# test_nudge_bg_session.sh — v0.63 nudge 真注入 smoke（dry_run + spawn fake claude）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"
export CCC_BG_NUDGE_DRY_RUN=1
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export CCC_BG_NUDGE_DIR="$TMP/bg"
export CCC_BG_SESSIONS_FILE="$TMP/state.json"

python3 - <<'PY'
import os
from pathlib import Path
from engine.active_tasks import (
    nudge_bg_session,
    register_bg_session,
    unregister_bg_session,
)

sid = "smoke-nudge-uuid"
register_bg_session("smoke-tid", "reviewer", sid, os.getpid(), "flash")
assert nudge_bg_session("reviewer", "smoke-tid", "smoke-msg") is True
nd = Path(os.environ["CCC_BG_NUDGE_DIR"])
assert (nd / f"{sid}.nudge").read_text() == "smoke-msg"
assert "dry_run" in (nd / f"{sid}.nudge.injected").read_text()
unregister_bg_session("reviewer", "smoke-tid")
print("nudge dry_run smoke OK")
PY

# spawn path with fake claude
export CCC_BG_NUDGE_DRY_RUN=0
FAKE="$TMP/fake-claude"
printf '%s\n' '#!/bin/sh' 'echo inject-ok' >"$FAKE"
chmod +x "$FAKE"
export CCC_CLAUDE_BIN="$FAKE"

python3 - <<'PY'
import os
import time
from pathlib import Path
from engine.active_tasks import (
    nudge_bg_session,
    register_bg_session,
    unregister_bg_session,
)

sid = "smoke-spawn-uuid"
register_bg_session("smoke-tid2", "reviewer", sid, os.getpid(), "flash")
assert nudge_bg_session("reviewer", "smoke-tid2", "spawn-msg") is True
nd = Path(os.environ["CCC_BG_NUDGE_DIR"])
inj = (nd / f"{sid}.nudge.injected").read_text()
assert "spawned" in inj, inj
# wait fake claude exit
time.sleep(0.3)
unregister_bg_session("reviewer", "smoke-tid2")
print("nudge spawn smoke OK")
PY

echo "ALL nudge smokes passed"

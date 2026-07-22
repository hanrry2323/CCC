#!/bin/bash
# tests/e2e/test_lpsn_flywheel.sh — LPSN P/S/N 平台门禁烟测
set -euo pipefail

echo "=== E2E: LPSN flywheel gates ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_DIR"

export PYTHONPATH="$SCRIPT_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}"

python3 - <<'PY'
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, "scripts")
from _intent_probe import extract_probe_commands, run_probes, is_allowed_verify_cmd
from chat_server.services import agent_mind, transfer_gate as tg

assert is_allowed_verify_cmd("python3 scripts/x.py")
assert is_allowed_verify_cmd("DRY_RUN=true .venv/bin/python scripts/x.py")
assert not is_allowed_verify_cmd("python3 scripts/x.py && rm -rf /")

with tempfile.TemporaryDirectory() as td:
    ws = Path(td)
    (ws / "scripts").mkdir()
    (ws / "scripts" / "probe.py").write_text("print('ok')\n")
    cmds = extract_probe_commands("## 验收\n- python3 scripts/probe.py\n")
    ok, ran = run_probes(ws, cmds)
    assert ok and ran[0]["ok"], ran

    agent_mind.merge_decided(
        ws,
        {
            "goals": [
                {
                    "id": "g-e2e",
                    "text": "e2e intent",
                    "exit_condition": "python3 scripts/probe.py",
                    "status": "planned",
                }
            ]
        },
        updated_by="human",
    )
    agent_mind.mark_goal_status(ws, "g-e2e", "stable", updated_by="human")
    assert agent_mind.unfinished_product_goals(agent_mind.load_decided(ws)) == []

    agent_mind.merge_decided(
        ws,
        {
            "goals": [
                {
                    "id": "g2",
                    "text": "next product",
                    "exit_condition": "python3 scripts/probe.py",
                    "status": "planned",
                }
            ]
        },
        updated_by="human",
    )
    err = tg.check_next_intent_gate(
        {
            "title": "other",
            "goal": "unrelated cluster",
            "acceptance": ["python3 -m pytest -q"],
            "pipeline": "dev",
        },
        ws,
    )
    assert err and err["code"] == "intent_not_stable"

    ok, errors = tg.validate_transfer_payload(
        {
            "title": "biz",
            "goal": "g",
            "acceptance": ["docs ok"],
            "pipeline": "dev",
            "feasibility": "ok",
            "project_id": "x",
        }
    )
    assert not ok and any(e["code"] == "missing_intent_probe" for e in errors)

print("LPSN e2e gates OK")
PY

echo "✓ LPSN flywheel e2e passed"

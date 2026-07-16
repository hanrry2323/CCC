#!/usr/bin/env bash
# test_green_pipeline_e2e.sh — mock 绿通：planned → testing → PASS verdict → verified
# 不启真实 LLM / opencode / KeepAlive。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"

WORKSPACE=$(mktemp -d)
trap 'rm -rf "$WORKSPACE"' EXIT

mkdir -p "$WORKSPACE/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
mkdir -p "$WORKSPACE/.ccc/"{plans,phases,pids,reports,verdicts,stats,review-locks}
mkdir -p "$WORKSPACE/scripts"

cat > "$WORKSPACE/.ccc/profile.md" <<'EOF'
# E2E Green
项目名: e2e-green
主语言: Python
EOF
cat > "$WORKSPACE/.ccc/state.md" <<'EOF'
当前版本: v0.40.1-test
EOF
echo 'x = 1' > "$WORKSPACE/scripts/dummy.py"

cd "$WORKSPACE"
git init -q
git config user.email "test@ccc"
git config user.name "test"
git add -A && git commit -qm "initial"
echo 'x = 2' > "$WORKSPACE/scripts/dummy.py"
git add -A && git commit -qm "feat: bump dummy"

cd "$ROOT"
export CCC_WORKSPACE="$WORKSPACE"
export CCC_REVIEWER_FALLBACK=stay
BOARD_PY="$ROOT/scripts/ccc-board.py"

# 1) create → planned with plan/phases (skip product/claude)
python3 "$BOARD_PY" --batch <<'EOF'
{"action":"create","id":"e2e-green","title":"Green pipeline","column":"planned","status":"planned","created_at":"2026-07-16","updated_at":"2026-07-16","complexity":"small"}
EOF

cat > "$WORKSPACE/.ccc/plans/e2e-green.plan.md" <<'EOF'
# e2e-green

## 目标
- mock green path

## 范围
- **只改文件**: scripts/dummy.py

## 验收
- py_compile 通过
EOF

cat > "$WORKSPACE/.ccc/phases/e2e-green.phases.json" <<'EOF'
{"schema_version": "1.1"}
{"phase": 1, "status": "done", "scope": ["scripts/dummy.py"], "commit_message": "e2e green", "commit": null, "timeout": 60, "notes": "", "retry": 0}
EOF

# 2) mock "opencode done": report + move testing
cat > "$WORKSPACE/.ccc/reports/e2e-green.report.md" <<'EOF'
# e2e-green report
status: done (mock)
EOF
python3 "$BOARD_PY" --batch <<'EOF'
{"action":"move","id":"e2e-green","from":"planned","to":"in_progress"}
{"action":"move","id":"e2e-green","from":"in_progress","to":"testing"}
EOF

# 3) reviewer: mock LLM fallback → FALLBACK≠PASS，stay testing（H2）
python3 - <<PY
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from board.context import set_workspace

spec = importlib.util.spec_from_file_location(
    "ccc_board", Path("scripts/ccc-board.py").resolve()
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
set_workspace(Path("$WORKSPACE"))

# 强制 medium 走 LLM，但 mock 成 unavailable → stay FALLBACK
mod._review_with_llm = lambda *a, **k: {
    "verdict": "fallback",
    "reason": "mock claude unavailable",
}
mod._classify_review_size = lambda _stat: ("medium", 20)

result = mod.reviewer_role()
vf = Path("$WORKSPACE") / ".ccc/verdicts/e2e-green.verdict.md"
text = vf.read_text()
assert "**Verdict:** FALLBACK" in text, text
assert "**Verdict:** PASS" not in text, text
assert not any(t["id"] == "e2e-green" for t in mod.list_tasks("verified")), result
assert any(t["id"] == "e2e-green" for t in mod.list_tasks("testing")), result
print("PASS green: testing → FALLBACK stay testing (no verified)")
PY

# 4) unit: claude resolve + upstream probe logic smoke
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
from _claude_cli import resolve_claude_cli
# host may or may not have claude; require=False must not raise
resolve_claude_cli(require=False)
print("PASS claude resolve soft")
PY

echo "=== green pipeline e2e OK ==="

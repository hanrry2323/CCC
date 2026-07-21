#!/usr/bin/env bash
# CCC Desktop stability gate：fast / full / dual
#
# fast  - 每次变更：Python compile + Desktop build + targeted unit tests
# full  - 发布前：所有 fast + Hub 端 Hub shell gate + Desktop stability report
# dual  - 发布候选：所有 full + 双机故障注入（依赖 M1 + Mac2017 网络可达）
#
# 内部复用现有 smoke / tests / build 脚本，不重复实现

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TIER="${1:-fast}"
case "$TIER" in
    fast|full|dual) ;;
    *)
        echo "usage: bash scripts/smoke-desktop-stability-gate.sh {fast|full|dual}" >&2
        exit 2
        ;;
esac

PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_DIR="${LOG_DIR:-var/diag/${TIER}-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$LOG_DIR"
REPORT="$LOG_DIR/stability.md"
SUMMARY="$LOG_DIR/summary.txt"

pass=0
fail=0
check() {
    local name="$1"
    shift
    if "$@"; then
        echo "PASS  $name" | tee -a "$SUMMARY"
        pass=$((pass + 1))
    else
        echo "FAIL  $name" | tee -a "$SUMMARY"
        fail=$((fail + 1))
    fi
}

echo "== CCC Desktop stability gate (tier=$TIER) ==" | tee -a "$SUMMARY"
echo "logs: $LOG_DIR" | tee -a "$SUMMARY"

# 1. 语法 / 编译
check "python syntax (agent-sidecar, hub services)" \
    bash -c "$PYTHON_BIN -m py_compile \
        scripts/ccc-agent-sidecar.py \
        scripts/chat_server/services/claude_client.py \
        scripts/chat_server/services/claude_session.py \
        scripts/chat_server/services/flow_events.py \
        scripts/chat_server/services/board_client.py \
        scripts/chat_server/routers/desktop.py \
        scripts/ccc-desktop-stability-report.py"

check "desktop build" bash -c "cd desktop && swift build"

# 2. 目标单测：侧车 + Desktop API + 稳定性报告
check "session manager unit" \
    bash -c "$PYTHON_BIN -m pytest tests/scripts/test_claude_session_manager.py -q --tb=line"
check "desktop api contract" \
    bash -c "$PYTHON_BIN -m pytest scripts/tests/test_desktop_api.py -q --tb=line"
check "desktop stability report" \
    bash -c "$PYTHON_BIN -m pytest tests/scripts/test_desktop_stability_report.py -q --tb=line"

# 3. fast 套件：现有 Desktop 稳态 + sidecar 存活 + 既有 Hub 端 entrypoint
check "smoke-desktop-stable" bash -c "bash scripts/smoke-desktop-stable.sh"
check "smoke-desktop-agent" bash -c "bash scripts/smoke-desktop-agent.sh"

if [[ "$TIER" == "fast" ]]; then
    $PYTHON_BIN scripts/ccc-desktop-stability-report.py --hours 24 --out "$REPORT" || true
    echo "report: $REPORT"
    echo "== gate (fast): $pass pass, $fail fail =="
    test "$fail" -eq 0
    exit 0
fi

# 4. full：加入 Hub 端门禁 + 完整单元 + 性能基线
check "smoke-hub-shell-gate" bash -c "bash scripts/smoke-hub-shell-gate.sh"
check "all unit tests" bash -c "$PYTHON_BIN -m pytest tests/scripts/ -q --tb=line --ignore=tests/scripts/test_claude_session_manager.py --ignore=tests/scripts/test_desktop_stability_report.py"
check "all hub tests" bash -c "$PYTHON_BIN -m pytest scripts/tests/ -q --tb=line --ignore=scripts/tests/test_desktop_api.py"

# 5. full：稳定性基线生成
$PYTHON_BIN scripts/ccc-desktop-stability-report.py --hours 24 --out "$REPORT" || true
check "stability report produced" bash -c "[ -s \"$REPORT\" ]"

if [[ "$TIER" == "full" ]]; then
    echo "report: $REPORT"
    echo "== gate (full): $pass pass, $fail fail =="
    test "$fail" -eq 0
    exit 0
fi

# 6. dual：双机故障注入（要求 M1 与 Mac2017 网络可达）
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"

check "hub reachable (dual)" \
    bash -c "curl -fsS --max-time 5 -u ccc:ccc \"$SERVER/api/desktop/config\" >/dev/null"
check "agent reachable (dual)" \
    bash -c "curl -fsS --max-time 3 \"$AGENT/health\" >/dev/null"
check "smoke-hub-outage-outbox (dual)" \
    bash -c "bash scripts/smoke-hub-outage-outbox.sh"
check "smoke-hub-empty-transfer-retry (dual)" \
    bash -c "bash scripts/smoke-hub-empty-transfer-retry.sh"

echo "report: $REPORT"
echo "== gate (dual): $pass pass, $fail fail =="
test "$fail" -eq 0

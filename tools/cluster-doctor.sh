#!/usr/bin/env bash
# tools/cluster-doctor.sh — CCC cluster health diagnostic
#
# P2-2 of v1.0 automation plan.
#
# Run:  bash tools/cluster-doctor.sh [--bus-url http://...]
#
# Exit codes:
#   0 = healthy
#   1 = bus unreachable
#   2 = no active nodes (cluster offline)
#   3 = some nodes stale (heartbeat > 90s)
#
# v3 portability: $BUS_URL expands in outer shell, no bash -c nesting.
set -euo pipefail

BUS_URL="${1:-http://127.0.0.1:9100}"
# Allow --bus-url form
if [[ "${1:-}" == "--bus-url" ]]; then
    BUS_URL="${2:-http://127.0.0.1:9100}"
fi

RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
NC=$'\033[0m'

echo "CCC cluster-doctor — $BUS_URL"
echo "================================"

# 1. bus liveness
echo
echo "[1/5] bus liveness"
if ! curl -fsS --max-time 3 "$BUS_URL/api/health" > /tmp/ccc-doctor-health.json 2>/dev/null; then
    echo "  ${RED}FAIL${NC}: bus unreachable at $BUS_URL"
    exit 1
fi
HEALTH=$(cat /tmp/ccc-doctor-health.json)
echo "  ${GREEN}OK${NC}: $HEALTH"

ACTIVE=$(python3 -c "import json,sys; print(json.load(open('/tmp/ccc-doctor-health.json')).get('active_nodes', 0))")
TOTAL=$(python3 -c "import json,sys; print(json.load(open('/tmp/ccc-doctor-health.json')).get('total_nodes', 0))")
echo "  active nodes: $ACTIVE / total: $TOTAL"

# 2. node list
echo
echo "[2/5] node list"
curl -fsS --max-time 3 "$BUS_URL/api/node/list" > /tmp/ccc-doctor-nodes.json 2>/dev/null
NODES=$(python3 -c "
import json
data = json.load(open('/tmp/ccc-doctor-nodes.json'))
for n in data['nodes']:
    print(n['node_id'])
")
if [ -z "$NODES" ]; then
    echo "  ${RED}FAIL${NC}: no active nodes"
    exit 2
fi
echo "$NODES"

# 3. heartbeat freshness
echo
echo "[3/5] heartbeat freshness (< 90s = healthy)"
STALE=0
python3 <<EOF > /tmp/ccc-doctor-freshness.txt
import json
data = json.load(open('/tmp/ccc-doctor-nodes.json'))
for n in data['nodes']:
    age = n['last_heartbeat_age_s']
    flag = 'OK' if age < 90 else 'STALE'
    print(f"  [{flag}] {n['node_id']} @ {n['host']}:{n['port']}  last_hb={age}s")
    if age >= 90:
        print('STALE')
EOF
cat /tmp/ccc-doctor-freshness.txt
if grep -q '^STALE$' /tmp/ccc-doctor-freshness.txt; then
    STALE=1
fi

# 4. capability matrix
echo
echo "[4/5] capability matrix"
python3 <<EOF > /tmp/ccc-doctor-matrix.txt
import json
data = json.load(open('/tmp/ccc-doctor-nodes.json'))
caps = sorted({c for n in data['nodes'] for c in n.get('capabilities', [])})
print(f"  {'capability':<24} {'nodes':<6}")
print(f"  {'-'*24} {'-'*6}")
for c in caps:
    nodes_with = [n['node_id'] for n in data['nodes'] if c in n.get('capabilities', [])]
    print(f"  {c:<24} {','.join(nodes_with):<6}")
EOF
cat /tmp/ccc-doctor-matrix.txt

# 5. summary
echo
echo "[5/5] verdict"
if [ "$STALE" -eq 1 ]; then
    echo "  ${YELLOW}WARN${NC}: some nodes stale (heartbeat > 90s)"
    exit 3
fi
if [ "$ACTIVE" -eq 0 ]; then
    echo "  ${RED}FAIL${NC}: cluster has 0 active nodes"
    exit 2
fi
echo "  ${GREEN}OK${NC}: cluster healthy ($ACTIVE active nodes, all fresh)"
exit 0

#!/usr/bin/env bash
# ccc-cleanup-test-residue.sh — 归档测试卡与 product pid 残留（不改控制面）
#
# Usage:
#   bash scripts/ccc-cleanup-test-residue.sh [--workspace PATH] [--dry-run]
#
# 默认 workspace：首个 engine_eligible app（常见 ccc-demo），或 CCC_CLEANUP_WS。
set -euo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY=false
WS="${CCC_CLEANUP_WS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=true; shift ;;
    --workspace) WS="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$WS" ]]; then
  WS=$(python3 - <<'PY'
import json
from pathlib import Path
p = Path.home() / ".ccc" / "workspaces.json"
if not p.is_file():
    print("")
    raise SystemExit
data = json.loads(p.read_text())
for w in data.get("workspaces") or []:
    if w.get("engine") or w.get("engine_eligible"):
        print(w.get("path") or "")
        break
PY
)
fi

if [[ -z "$WS" || ! -d "$WS" ]]; then
  echo "ERROR: workspace not found (set --workspace or CCC_CLEANUP_WS)" >&2
  exit 1
fi

TS=$(date +%Y%m%d-%H%M%S)
Q="$WS/.ccc/quarantines/test-residue-$TS"

is_test_name() {
  case "$1" in
    desktop-smoke*|desktop-golive*|boundary-e2e*|selfcheck*|e2e-*|deploy-smoke*|full-e2e*|smoke*|agent-smoke*|ops-adopt*|inj-*)
      return 0 ;;
    *) return 1 ;;
  esac
}

echo "== cleanup test residue =="
echo "workspace: $WS"
echo "quarantine: $Q"
echo "dry_run: $DRY"

moved=0
shopt -s nullglob

for col in backlog planned in_progress testing verified released abnormal; do
  dir="$WS/.ccc/board/$col"
  [[ -d "$dir" ]] || continue
  for f in "$dir"/*.jsonl; do
    base=$(basename "$f")
    is_test_name "$base" || continue
    if $DRY; then
      echo "DRY board/$col/$base"
    else
      mkdir -p "$Q/board/$col"
      mv "$f" "$Q/board/$col/"
      moved=$((moved + 1))
    fi
  done
done

for sub in plans phases reports verdicts; do
  src="$WS/.ccc/$sub"
  [[ -d "$src" ]] || continue
  for f in "$src"/*; do
    [[ -f "$f" ]] || continue
    base=$(basename "$f")
    # strip common suffixes for prefix match
    stem="${base%%.*}"
    is_test_name "$base" || is_test_name "$stem" || continue
    if $DRY; then
      echo "DRY $sub/$base"
    else
      mkdir -p "$Q/$sub"
      mv "$f" "$Q/$sub/"
      moved=$((moved + 1))
    fi
  done
done

if [[ -d "$WS/.ccc/pids" ]]; then
  for f in "$WS/.ccc/pids"/*; do
    [[ -e "$f" ]] || continue
    base=$(basename "$f")
    stem="${base%%.*}"
    is_test_name "$base" || is_test_name "$stem" || continue
    if $DRY; then
      echo "DRY pids/$base"
    else
      mkdir -p "$Q/pids"
      mv "$f" "$Q/pids/"
      moved=$((moved + 1))
    fi
  done
fi

if ! $DRY; then
  PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 - <<PY
from pathlib import Path
import sys
sys.path.insert(0, "${CCC_HOME}/scripts")
from _board_store import FileBoardStore
print("index", FileBoardStore(Path(r"${WS}")).update_index())
PY
  mkdir -p "${HOME}/.ccc"
  date -u +%Y-%m-%dT%H:%M:%SZ > "${HOME}/.ccc/engine.wake" 2>/dev/null || true
fi

echo "moved=$moved"
echo "done (control plane untouched)"

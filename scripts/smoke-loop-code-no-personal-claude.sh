#!/usr/bin/env bash
# Phase2：PATH 无个人 claude 时，sidecar 仍为 loop-code（不依赖 Hub）
# 用法：bash scripts/smoke-loop-code-no-personal-claude.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"

echo "== smoke-loop-code-no-personal-claude agent=${AGENT} =="

# 1) 宿主机不应再发现个人 claude（PATH 内）
if command -v claude >/dev/null 2>&1; then
  echo "FAIL: command -v claude still resolves: $(command -v claude)"
  echo "  Run Phase2 retire runbook (docs/product/loop-code-ownership-cut-phase2-brief.md)"
  exit 1
fi
echo "OK no personal claude on PATH"

# 2) vendor loop-code 必须在
if [[ ! -x "${ROOT}/vendor/loop-code/cli" ]]; then
  echo "FAIL: missing ${ROOT}/vendor/loop-code/cli"
  exit 1
fi
echo "OK vendor/loop-code/cli"

# 3) sidecar health
HEALTH="$(curl -sf -m 5 "${AGENT%/}/health")"
echo "$HEALTH" | python3 -c "
import json,sys
d=json.load(sys.stdin)
rt=d.get('agent_runtime') or ''
cfg=d.get('config_dir') or ''
assert d.get('ok') is True, d
assert rt == 'loop-code', f'want loop-code got {rt!r}'
assert '.ccc/loop-code' in str(cfg).replace('\\\\', '/'), f'bad config_dir {cfg!r}'
print('OK sidecar health runtime=loop-code config_dir=', cfg)
"

# 4) 严格 resolve：即使 PATH 塞假 claude 也不该选中（本机无 vendor 时）
CCC_EXECUTOR=loop-code env -u CCC_CLAUDE_BIN python3 -c "
import sys
sys.path.insert(0, 'scripts')
from _claude_cli import resolve_claude_cli, path_is_loop_code
p = resolve_claude_cli(require=True)
assert path_is_loop_code(p), p
print('OK resolve_claude_cli →', p)
"

echo "== smoke-loop-code-no-personal-claude PASS =="

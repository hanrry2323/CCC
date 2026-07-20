#!/bin/bash
# smoke-executor-stack.sh — Server 侧执行器栈冒烟（relay + CLI 解析 + opencode）
set -euo pipefail
CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}"
FAIL=0

echo "== CCC smoke-executor-stack =="
echo "CCC_HOME=$CCC_HOME"
echo "note: ai-loop-router :4000/:4002 retired; Claude→MiniMax, OpenCode→local config"

echo "-- resolve_claude_cli (default) --"
DEFAULT_BIN="$(
  env -u CCC_CLAUDE_BIN -u CCC_EXECUTOR python3 -c "from _claude_cli import resolve_claude_cli; print(resolve_claude_cli(require=False) or '')"
)"
if [[ -n "$DEFAULT_BIN" && -x "$DEFAULT_BIN" ]]; then
  echo "OK  default CLI = $DEFAULT_BIN"
else
  echo "FAIL default CLI unresolved"
  FAIL=1
fi

echo "-- resolve_claude_cli (loop-code) --"
LC="${CCC_HOME}/vendor/loop-code/cli"
REAL="$(python3 -c "from pathlib import Path; print(Path('${LC}').resolve())" 2>/dev/null || echo "")"
if [[ ! -x "$LC" ]]; then
  echo "FAIL loop-code missing executable: $LC (SSOT 方案 Agent; run scripts/install-executor-loop-code.sh)"
  FAIL=1
else
  GOT="$(
    CCC_EXECUTOR=loop-code env -u CCC_CLAUDE_BIN python3 -c "from _claude_cli import resolve_claude_cli; print(resolve_claude_cli(require=True))"
  )"
  if [[ "$GOT" == "$REAL" ]]; then
    echo "OK  CCC_EXECUTOR=loop-code → $GOT"
  else
    echo "FAIL loop-code resolve got=$GOT want=$REAL"
    FAIL=1
  fi
fi

echo "-- opencode --"
if command -v opencode >/dev/null 2>&1; then
  echo "OK  opencode = $(command -v opencode)"
elif [[ -x "${HOME}/.npm-global/bin/opencode" ]]; then
  echo "OK  opencode = ${HOME}/.npm-global/bin/opencode"
else
  echo "FAIL opencode not found"
  FAIL=1
fi

if [[ "${SMOKE_CLAUDE_P:-}" == "1" && -n "$DEFAULT_BIN" ]]; then
  echo "-- claude -p smoke --"
  BASE="${ANTHROPIC_BASE_URL:-https://api.minimaxi.com/anthropic}"
  if printf 'Reply with exactly: OK\n' | ANTHROPIC_BASE_URL="$BASE" timeout 90 "$DEFAULT_BIN" -p --model "${ANTHROPIC_MODEL:-MiniMax-M3}" 2>/dev/null | tail -5; then
    echo "OK  claude -p"
  else
    # macOS may lack timeout
    if printf 'Reply with exactly: OK\n' | ANTHROPIC_BASE_URL="$BASE" "$DEFAULT_BIN" -p --model "${ANTHROPIC_MODEL:-MiniMax-M3}" 2>/dev/null | tail -5; then
      echo "OK  claude -p"
    else
      echo "FAIL claude -p"
      FAIL=1
    fi
  fi
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS"
exit 0

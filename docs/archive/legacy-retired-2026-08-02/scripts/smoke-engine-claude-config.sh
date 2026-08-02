#!/usr/bin/env bash
# Phase3：Engine 私有配置家 ~/.ccc/engine-claude
# 用法：
#   bash scripts/smoke-engine-claude-config.sh           # 本机（或 2017）
#   ssh mac2017 'cd ~/program/CCC && bash scripts/smoke-engine-claude-config.sh'
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.ccc/engine-claude}"

echo "== smoke-engine-claude-config cfg=${CFG} =="

python3 - <<PY
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from _claude_cli import ensure_engine_claude_config_dir, default_engine_claude_config_dir
from _executor import _claude_env

root = ensure_engine_claude_config_dir(Path("${CFG}").expanduser())
assert root.is_dir(), root
assert (root / "CLAUDE.md").is_file(), "missing CLAUDE.md"
assert (root / "settings.json").is_file(), "missing settings.json"
assert "engine-claude" in str(root) or str(root) == str(Path("${CFG}").expanduser()), root
env = _claude_env()
assert "engine-claude" in env.get("CLAUDE_CONFIG_DIR", "").replace("\\\\", "/"), env.get("CLAUDE_CONFIG_DIR")
print("OK ensure + _claude_env CLAUDE_CONFIG_DIR=", env["CLAUDE_CONFIG_DIR"])
print("OK default=", default_engine_claude_config_dir())
PY

echo "== smoke-engine-claude-config PASS =="

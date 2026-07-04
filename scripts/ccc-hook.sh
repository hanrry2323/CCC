#!/bin/bash
# ccc-hook — Claude Code pre-tool hook
# Reads a JSON event from stdin, checks if the tool targets .ccc/ paths,
# and returns a JSON decision: {"decision": "allow"|"warn", "reason": "..."}
#
# Usage in claude_code settings.json:
#   "preToolUseHook": "bash /path/to/ccc-hook.sh"

set -euo pipefail

# Read stdin (single JSON line)
INPUT="$(cat)"

# Extract file_path using python for robust JSON parsing
FILE_PATH="$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    tool_input = d.get('tool_input', {})
    fp = tool_input.get('file_path', '')
    print(fp)
except Exception:
    print('')
")"

# No file_path → allow (e.g. read/search tool)
if [ -z "$FILE_PATH" ]; then
  echo '{"decision": "allow", "reason": "no file_path in tool_input"}'
  exit 0
fi

# Allow .ccc/ paths (Planner-managed metadata)
if [[ "$FILE_PATH" == .ccc/* ]]; then
  echo "{\"decision\": \"allow\", \"reason\": \"ccc metadata: $FILE_PATH\"}"
  exit 0
fi

# Allow symlink and scripts dir paths
if [[ "$FILE_PATH" == scripts/* ]] || [[ "$FILE_PATH" == templates/* ]]; then
  echo "{\"decision\": \"allow\", \"reason\": \"ccc framework file: $FILE_PATH\"}"
  exit 0
fi

# Everything else → warn (source code, etc.)
echo "{\"decision\": \"warn\", \"reason\": \"source code modification detected: $FILE_PATH. Use Executor for code changes, not Planner.\"}"

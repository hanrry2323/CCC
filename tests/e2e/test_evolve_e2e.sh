#!/usr/bin/env bash
# CCC Evolve E2E — 验证进化闭环全链路
# 测试步骤：
#   1. 创建临时 workspace 并初始化 board
#   2. 写入有问题的 Python 文件（死代码 / 高复杂度 / 安全问题）
#   3. 运行 evolve_run()
#   4. 验证 backlog 有 task，第二次跑 posted=0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_DIR"

WS=$(mktemp -d /tmp/ccc-evolve-e2e-XXXXX)
trap 'rm -rf "$WS"' EXIT

echo "=== E2E: Evolve ==="
echo "workspace: $WS"

# 1. 初始化 workspace（board 列 + evolve 目录；FileBoardStore 也会兜底建列）
mkdir -p "$WS/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
mkdir -p "$WS/.ccc/evolve"
printf '%s\n' '{"backlog":0,"planned":0,"in_progress":0,"testing":0,"verified":0,"released":0}' \
  > "$WS/.ccc/board/index.json"

git -C "$WS" init -q
git -C "$WS" config user.email "test@ccc"
git -C "$WS" config user.name "CCC Test"

# 2. 写入测试代码（死代码 + 高复杂度 + 安全问题）
cat > "$WS/test_code.py" << 'PYEOF'
import os
import sys
import subprocess
import pickle

unused_var = "dead"

def deep_switch(x):
    if x == 1:
        return "a"
    elif x == 2:
        return "b"
    elif x == 3:
        return "c"
    elif x == 4:
        return "d"
    elif x == 5:
        return "e"
    elif x == 6:
        return "f"
    elif x == 7:
        return "g"
    elif x == 8:
        return "h"
    elif x == 9:
        return "i"
    elif x == 10:
        return "j"
    elif x == 11:
        return "k"
    elif x == 12:
        return "l"
    return "z"

def user_proxy():
    # 安全红线：shell=True + pickle + eval
    result = subprocess.run("echo hello", shell=True)
    data = pickle.loads(b"test")
    cmd = eval("1+1")
    return cmd, result, data

def old_unused():
    return None
PYEOF

git -C "$WS" add -A
git -C "$WS" commit -q -m "init test"

# 3. 运行 evolve_run
python3 - <<PY
import sys
sys.path.insert(0, "scripts")
from _evolve import evolve_run

result = evolve_run("$WS", max_tasks=3)
print(f'posted={result["posted"]}')
print(f'total={result["total"]}')
print(f'filtered={result["filtered"]}')
print(f'tasks={result.get("posted_tasks", [])}')
assert result["posted"] > 0, f'应该有发现被投递到 backlog，got {result}'
print("OK evolve_run 成功投递")
PY

# 4. 验证 backlog
count=$(find "$WS/.ccc/board/backlog" -name 'evolve-*.jsonl' 2>/dev/null | wc -l | tr -d ' ')
echo "backlog evolve tasks: $count"
if [ "$count" -gt 0 ]; then
  echo "OK backlog 有 evolve 任务"
  ls "$WS/.ccc/board/backlog"/evolve-*.jsonl | head -5
else
  echo "FAIL backlog 无 evolve 任务"
  ls -la "$WS/.ccc/board/backlog/" || true
  exit 1
fi

# 5. 验证去重（第二次跑 posted=0）
python3 - <<PY
import sys
sys.path.insert(0, "scripts")
from _evolve import evolve_run

result = evolve_run("$WS", max_tasks=3)
assert result["posted"] == 0, f'第二次跑应该 posted=0，实际 {result["posted"]}'
print("OK 去重成功")
PY

# 6. fingerprints 文件存在
if [ -f "$WS/.ccc/evolve/fingerprints.json" ]; then
  echo "OK fingerprints.json 已写入"
else
  echo "FAIL fingerprints.json 缺失"
  exit 1
fi

echo "=== E2E PASS ==="

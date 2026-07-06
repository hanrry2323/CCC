#!/bin/bash
# ccc-zcode-bridge.sh — CCC ZCode session spawn wrapper (v1.2.1)
#
# 封装 claude -p + BigModel provider,用于 ZCode 环境调度独立 session。
# 解决 runtime-zcode.md 原"无 claude -p 等效"说法的不准确(本系统实测 claude 在 PATH)。
#
# 用法:
#   bash scripts/ccc-zcode-bridge.sh <workspace> <task> <role> [--dry-run]
#     role ∈ {executor, verifier}
#     --dry-run: 只生成 UUID + 验证 prompt,不真跑 claude
#
# 红线:
#   6  (Planner/Verifier 隔离): 每个 --session-id UUID 唯一
#   9  (卡死止损): watchdog 前置 + timeout 600
#   11 (verdict 真文件): Verifier 角色必落 .ccc/verdicts/<task>.verdict.md
#   Lesson 27: stdin 喂 prompt,不写 claude -p "..."
#
# 输出:
#   - UUID 落盘 .ccc/plans/<task>-<role>-session-id.txt (可追溯)
#   - spawn 报告落 .ccc/dispatches/spawn-<task>-<role>-<UUID>.json (红线 10)
#   - claude stdout/stderr 落 /tmp/ccc-zcode-bridge-<UUID>.log
#
# 环境依赖:
#   - claude 在 PATH (实测 /Users/apple/.local/bin/claude)
#   - ANTHROPIC_BASE_URL 默认指向 https://open.bigmodel.cn/api/anthropic
#     可被环境变量 ANTHROPIC_BASE_URL 覆盖
#   - API key 来自 ~/.zcode/v2/credentials.json 或环境变量 ANTHROPIC_AUTH_TOKEN

set -uo pipefail

# --- 参数解析 ---
DRY_RUN=0
WORKSPACE=""
TASK=""
ROLE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      cat <<'EOF'
ccc-zcode-bridge.sh — ZCode session spawn wrapper

用法:
  bash scripts/ccc-zcode-bridge.sh <workspace> <task> <role> [--dry-run]

参数:
  workspace  项目根路径(绝对路径)
  task       CCC 任务 ID(kebab-case)
  role       executor | verifier

选项:
  --dry-run  生成 UUID + 校验 prompt 文件,不真启动 claude
  -h, --help 显示本帮助

环境变量:
  ANTHROPIC_BASE_URL    默认 https://open.bigmodel.cn/api/anthropic
  ANTHROPIC_AUTH_TOKEN  GLM API key(默认从 ~/.zcode/v2/credentials.json 读)
  CLAUDE_MODEL          默认 glm-5(可改 claude-sonnet-4-5 等)

退出码:
  0 = spawn 成功
  1 = 缺 prompt / watchdog FAIL / claude FAIL
  2 = 参数错误
EOF
      exit 0 ;;
    *)
      if [[ -z "$WORKSPACE" ]]; then WORKSPACE="$1"; shift
      elif [[ -z "$TASK" ]]; then TASK="$1"; shift
      elif [[ -z "$ROLE" ]]; then ROLE="$1"; shift
      else echo "未知参数: $1" >&2; exit 2
      fi ;;
  esac
done

if [[ -z "$WORKSPACE" || -z "$TASK" || -z "$ROLE" ]]; then
  echo "用法: bash ccc-zcode-bridge.sh <workspace> <task> <role> [--dry-run]" >&2
  exit 2
fi

if [[ "$ROLE" != "executor" && "$ROLE" != "verifier" ]]; then
  echo "ERROR: role 必须是 executor 或 verifier (got: $ROLE)" >&2
  exit 2
fi

# --- 路径常量 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCC_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
WATCHDOG="$CCC_HOME/scripts/executor-watchdog.sh"
PROMPT_FILE="$WORKSPACE/.ccc/plans/${TASK}-${ROLE}-prompt.txt"
SID_FILE="$WORKSPACE/.ccc/plans/${TASK}-${ROLE}-session-id.txt"
DISPATCH_DIR="$WORKSPACE/.ccc/dispatches"

# --- Provider 配置 (ZCode 默认走 BigModel/GLM) ---
ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://open.bigmodel.cn/api/anthropic}"
CLAUDE_MODEL="${CLAUDE_MODEL:-glm-5}"

# --- 凭证加载 (优先级: env > ~/.zcode/v2/credentials.json > ~/.config/ccc/credentials) ---
if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
  for cred_file in "$HOME/.zcode/v2/credentials.json" "$HOME/.config/ccc/credentials.json"; do
    if [[ -f "$cred_file" ]]; then
      # 简单 grep 提取,避免 jq 依赖
      TOKEN=$(grep -oE '"(api_key|access_token|token)"[[:space:]]*:[[:space:]]*"[^"]+"' "$cred_file" 2>/dev/null \
        | head -1 | sed -E 's/.*"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
      if [[ -n "$TOKEN" ]]; then
        export ANTHROPIC_AUTH_TOKEN="$TOKEN"
        break
      fi
    fi
  done
fi

# --- UUID 管理(读现有或新生成) ---
ensure_uuid() {
  mkdir -p "$(dirname "$SID_FILE")"
  if [[ -f "$SID_FILE" ]] && [[ -s "$SID_FILE" ]]; then
    cat "$SID_FILE"
  else
    if command -v uuidgen >/dev/null 2>&1; then
      uuidgen | tr '[:upper:]' '[:lower:]'
    else
      python3 -c "import uuid; print(uuid.uuid4())"
    fi
  fi
}

UUID="$(ensure_uuid)"
echo "$UUID" > "$SID_FILE"

# --- Dispatch 目录 ---
mkdir -p "$DISPATCH_DIR"
SPAWN_REPORT="$DISPATCH_DIR/spawn-${TASK}-${ROLE}-${UUID}.json"

# --- 写 spawn 报告骨架(Step 0,先创建避免异常退出无产物)---
TIMESTAMP=$(date +%s)
cat > "$SPAWN_REPORT" <<EOF
{
  "task": "$TASK",
  "role": "$ROLE",
  "session_id": "$UUID",
  "workspace": "$WORKSPACE",
  "model": "$CLAUDE_MODEL",
  "anthropic_base_url": "$ANTHROPIC_BASE_URL",
  "dry_run": $DRY_RUN,
  "started_at": $TIMESTAMP,
  "status": "pending"
}
EOF

# --- 校验 prompt 文件存在(红线 2 验收可执行) ---
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "ERROR: prompt 文件不存在: $PROMPT_FILE" >&2
  echo "请先由 Planner 写出 ${TASK}-${ROLE}-prompt.txt (参见 templates/executor-prompt.template.md)" >&2
  python3 -c "
import json
r = json.load(open('$SPAWN_REPORT'))
r['status'] = 'failed'
r['failure_reason'] = 'prompt_file_missing'
r['prompt_file'] = '$PROMPT_FILE'
json.dump(r, open('$SPAWN_REPORT','w'), indent=2)
"
  exit 1
fi

PROMPT_LINES=$(wc -l < "$PROMPT_FILE" | tr -d ' ')

# --- Dry-run 模式 ---
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "=== ccc-zcode-bridge.sh (DRY-RUN) ==="
  echo "  workspace:     $WORKSPACE"
  echo "  task:          $TASK"
  echo "  role:          $ROLE"
  echo "  session_id:    $UUID (saved to $SID_FILE)"
  echo "  prompt_file:   $PROMPT_FILE ($PROMPT_LINES 行)"
  echo "  model:         $CLAUDE_MODEL"
  echo "  base_url:      $ANTHROPIC_BASE_URL"
  echo "  spawn_report:  $SPAWN_REPORT"
  echo "  watchdog:      $WATCHDOG"
  echo ""
  echo "[dry-run] 将执行 (不真跑):"
  echo "  bash $WATCHDOG || exit 1"
  echo "  ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL \\"
  echo "    timeout 600 claude -p \\"
  echo "      --permission-mode bypassPermissions \\"
  echo "      --dangerously-skip-permissions \\"
  echo "      --model $CLAUDE_MODEL \\"
  echo "      --add-dir $WORKSPACE \\"
  echo "      --session-id $UUID \\"
  echo "      < $PROMPT_FILE"
  echo ""

  python3 -c "
import json
r = json.load(open('$SPAWN_REPORT'))
r['status'] = 'dry-run'
r['prompt_lines'] = $PROMPT_LINES
json.dump(r, open('$SPAWN_REPORT','w'), indent=2)
"
  echo "[dry-run] 全部校验通过,UUID 已分配。"
  exit 0
fi

# --- 前置 watchdog (红线 9 卡死止损) ---
echo "[bridge] running watchdog pre-check..."
if ! bash "$WATCHDOG" >/tmp/ccc-zcode-watchdog-${UUID}.log 2>&1; then
  WD_EXIT=$?
  if [[ $WD_EXIT -eq 3 ]]; then
    echo "[bridge] watchdog 已自动清理(--force-kill),继续启动" >&2
  elif [[ $WD_EXIT -eq 2 ]]; then
    echo "[bridge] watchdog 严重失败 (exit=$WD_EXIT),拒绝启动 Executor" >&2
    python3 -c "
import json
r = json.load(open('$SPAWN_REPORT'))
r['status'] = 'failed'
r['failure_reason'] = 'watchdog_serious'
r['watchdog_exit'] = $WD_EXIT
json.dump(r, open('$SPAWN_REPORT','w'), indent=2)
"
    cat /tmp/ccc-zcode-watchdog-${UUID}.log >&2
    exit 1
  else
    echo "[bridge] watchdog 警告 (exit=$WD_EXIT),继续启动但已记录" >&2
  fi
fi

# --- Claude -p spawn (Lesson 27: stdin 喂 prompt) ---
LOG_FILE="/tmp/ccc-zcode-bridge-${UUID}.log"
echo "[bridge] spawning claude -p role=$ROLE session=$UUID model=$CLAUDE_MODEL"

set +e
ANTHROPIC_BASE_URL="$ANTHROPIC_BASE_URL" \
  timeout 600 \
  claude -p \
    --permission-mode bypassPermissions \
    --dangerously-skip-permissions \
    --model "$CLAUDE_MODEL" \
    --add-dir "$WORKSPACE" \
    --session-id "$UUID" \
    < "$PROMPT_FILE" \
  > "$LOG_FILE" 2>&1
CLAUDE_EXIT=$?
set -e

# --- 写最终 spawn 报告 ---
python3 - "$SPAWN_REPORT" "$CLAUDE_EXIT" "$LOG_FILE" <<'PYEOF'
import json, os, sys
report_path, claude_exit, log_file = sys.argv[1], int(sys.argv[2]), sys.argv[3]
r = json.load(open(report_path))
r["claude_exit"] = claude_exit
r["log_file"] = log_file
r["finished_at"] = int(os.path.getmtime(log_file)) if os.path.exists(log_file) else 0
r["status"] = "success" if claude_exit == 0 else "failed"
if claude_exit != 0:
    r["failure_reason"] = f"claude_exit_{claude_exit}"
json.dump(r, open(report_path, "w"), indent=2)
PYEOF

# --- 输出关键指标 ---
echo "[bridge] claude exit=$CLAUDE_EXIT"
echo "[bridge] log=$LOG_FILE"
echo "[bridge] report=$SPAWN_REPORT"
echo "[bridge] session_id=$UUID"

if [[ $CLAUDE_EXIT -eq 0 ]]; then
  echo "[bridge] OK"
  exit 0
else
  echo "[bridge] FAIL (claude exit=$CLAUDE_EXIT), tail of log:" >&2
  tail -20 "$LOG_FILE" >&2 || true
  exit 1
fi
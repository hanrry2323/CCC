#!/bin/bash
# 后段验收席执行体（Claude Code CLI wrapper）。
# JSON verdict 是唯一判定工件；markdown 仅供人读与兼容旧消费者。
# 用法：scripts/cc-auditor.sh <card_path> <work_id> <worktree> [role] [biz_worktree]

set -uo pipefail
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CCC_ROOT="$(cd "$_SELF/.." && pwd -P)"

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-验收席}"
BIZ_WORKTREE="${5:-}"
[[ "$WORKTREE" == "__CCC_EMPTY__" ]] && WORKTREE=""
[[ "$BIZ_WORKTREE" == "__CCC_EMPTY__" ]] && BIZ_WORKTREE=""

case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*:*":/usr/local/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:/usr/local/bin:$PATH" ;;
esac
CLAUDE_BIN="${CCC_BRAIN_CLAUDE_BIN:-claude}"
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || {
  echo "[cc-auditor] ERROR: claude CLI 不在 PATH" >&2
  exit 127
}

# claude CLI 读取裸根；phase2/探针可能注入完整 /v1/messages 端点。
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:3456}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-Code}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-dummy-placeholder}"

REPO_ROOT="$(cd "$_SELF/.." && pwd -P)"
cd "$REPO_ROOT"
AUDIT_CARD="$CARD_PATH"
TEST_WORKDIR="${BIZ_WORKTREE:-${WORKTREE:-$REPO_ROOT}}"
if [[ ! -d "$TEST_WORKDIR" ]]; then
  echo "[cc-auditor] WARN: test_workdir 不存在，回落主仓: ${TEST_WORKDIR} -> ${REPO_ROOT}" >&2
  TEST_WORKDIR="$REPO_ROOT"
fi
LOG_DIR="${EXECUTOR_LOG_DIR:-${LOG_DIR:-$HOME/.ccc/logs/exec}}"
mkdir -p "$LOG_DIR"
VERDICT_JSON="$LOG_DIR/${WORK_ID}-audit-verdict.json"
VERDICT_FILE="$LOG_DIR/${WORK_ID}-audit-verdict.md"
RESULT_FILE="$LOG_DIR/${WORK_ID}-ccc-result.md"
TMP_OUTPUT="$(mktemp)"
trap 'rm -f "$TMP_OUTPUT"' EXIT

write_protocol_reject() {
  local reason="$1"
  local json_prefix="${2:-0}"
  # JSON verdict 是主契约：机械门禁（维护区/测试）失败也要产出合法 JSON REJECT，
  # 否则 phase2 读不到 JSON → 误判 protocol 失败并累计到「待人工」。
  # reason 经 python json.dumps 转义（防引号/反斜杠破坏 JSON）。
  if [ "$json_prefix" = "1" ]; then
    printf 'protocol：%s' "$reason" | python3 -c 'import json,sys; print(json.dumps({"verdict":"REJECT","reason":sys.stdin.read(),"findings":[]}, ensure_ascii=False))' > "$VERDICT_JSON"
  else
    printf '%s' "$reason" | python3 -c 'import json,sys; print(json.dumps({"verdict":"REJECT","reason":sys.stdin.read(),"findings":[]}, ensure_ascii=False))' > "$VERDICT_JSON"
  fi
  # Markdown 保留 protocol 标签供人读；JSON reason 是否带 protocol 前缀取决于调用方：
  # 机械门禁失败（业务 REJECT）不带，LLM 未产出合法 verdict（协议失败）带——phase2
  # 按 reason 前缀判定：带 protocol：走修复轮路由，不烧业务预算（宪章修订1）。
  printf '机审：不通过（protocol：%s）\n' "$reason" > "$VERDICT_FILE"
}

# 机械门禁一：维护区四问。
if [ -f "$AUDIT_CARD" ]; then
  MG_PROBLEMS="$(python3 - "$AUDIT_CARD" "$(pwd)" <<'PY'
import sys
sys.path.insert(0, sys.argv[2])
try:
    from server.board.docgate import verify_maintenance
    ok, problems = verify_maintenance(sys.argv[1], sys.argv[2])
    print("；".join(problems) or "维护区未完成") if not ok else None
    sys.exit(0 if ok else 2)
except Exception as exc:
    print(f"维护区机械校验异常: {exc}")
    sys.exit(3)
PY
  )" || MG_RC=$?
  if [ "${MG_RC:-0}" = "2" ]; then
    write_protocol_reject "维护区未完成：${MG_PROBLEMS:-未知原因}"
    exit 2
  elif [ "${MG_RC:-0}" != "0" ]; then
    echo "[cc-auditor] 机械门禁（维护区）异常" >&2
    exit 3
  fi
  unset MG_RC
fi

# 机械门禁二：测试真实性截获。
_TE_EXEC_LOG_DIR="${EXECUTOR_LOG_DIR:-}"
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_CFG="${CCC_CONFIG_ENV:-$_CCC_ROOT/server/config/config.env}"
  if [[ -f "$_TE_CFG" ]]; then
    _TE_EXEC_LOG_DIR="$(grep -E '^\s*EXECUTOR_LOG_DIR\s*=' "$_TE_CFG" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | xargs 2>/dev/null || true)"
  fi
fi
_TE_EXEC_LOG_DIR="${_TE_EXEC_LOG_DIR:-$HOME/.ccc/logs/exec}"
_TE_EVIDENCE_LOG="${_TE_EXEC_LOG_DIR}/${WORK_ID}.test-evidence.log"
if [[ -f "$AUDIT_CARD" && -d "$TEST_WORKDIR" ]]; then
  if ! bash "$_CCC_ROOT/scripts/test-evidence.sh" "$AUDIT_CARD" "$TEST_WORKDIR" "$_TE_EVIDENCE_LOG"; then
    _TE_RC=$?
    write_protocol_reject "测试真实失败：见 $_TE_EVIDENCE_LOG"
    exit 2
  fi
fi

if [[ ! -f "$RESULT_FILE" ]]; then
  echo "[cc-auditor] 前置缺失：执行结果工件不存在 $RESULT_FILE" >&2
  exit 3
fi

PROMPT="你是后段验收席（Claude Code CLI）。任务卡（主仓只读）：
${AUDIT_CARD}
执行结果工件：
${RESULT_FILE}
（work ${WORK_ID}，角色：${ROLE}）已回写，待验收。

按对抗式审查执行：范围核对、对抗式找茬、P0/P1/P2 分级、维护区四问核对。
主仓卡只读，禁止写卡/写仓，禁止运行 Bash/Edit。
审计结束必须使用 Write 工具写 JSON 到 ${VERDICT_JSON}，严格符合：
{\"verdict\":\"PASS|REJECT\",\"reason\":\"一句话结论\",\"findings\":[{\"id\":\"F1\",\"severity\":\"P0|P1|P2\",\"file\":\"相对路径\",\"line\":0,\"note\":\"可复现说明\"}]}
审查正文（证据四段）另写 ${VERDICT_FILE}，仅供人读，非判定依据。结论必须落到文件，不得只输出 stdout。"

set +e
if [ -n "${ANTHROPIC_BASE_URL:-}" ]; then
  ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL%/v1/messages}"
  export ANTHROPIC_BASE_URL
fi
# 每轮审计必须从空 verdict 工件开始，避免复用上一轮遗留结论。
rm -f "$VERDICT_JSON" "$VERDICT_FILE" || true
attempt=0
CC_AUDITOR_ATTEMPTS="${CC_AUDITOR_ATTEMPTS:-3}"
while [ "$attempt" -lt "$CC_AUDITOR_ATTEMPTS" ]; do
  attempt=$((attempt+1))
  "$CLAUDE_BIN" -p "$PROMPT" \
    --output-format text \
    --max-turns "${CC_AUDITOR_MAX_TURNS:-30}" \
    --permission-mode bypassPermissions \
    --allowedTools "Read Write" \
    > "$TMP_OUTPUT" 2>&1
  rc=$?
  if [ -s "$VERDICT_JSON" ]; then
    echo "[cc-auditor] attempt ${attempt}: JSON verdict 工件已产出（claude rc=${rc}）" >&2
    break
  fi
  if [ "$attempt" -lt "$CC_AUDITOR_ATTEMPTS" ]; then
    echo "[cc-auditor] attempt ${attempt}/${CC_AUDITOR_ATTEMPTS}: 无 JSON verdict，30s 后重试" >&2
    sleep 30
  fi
done
set -e
cat "$TMP_OUTPUT"

# 用 Python 校验 schema；无合法 JSON 一律显式 REJECT，绝不把 stdout 当结论。
# LLM 未产出合法 verdict → 协议失败（protocol：前缀），走修复轮路由，不烧业务预算。
if [ ! -s "$VERDICT_JSON" ]; then
  write_protocol_reject "JSON verdict 缺失或非法（claude 未产出合法 verdict）" 1
  exit 2
fi
VALIDATION="$(python3 - "$VERDICT_JSON" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict): raise ValueError("root")
    if value.get("verdict") not in {"PASS", "REJECT"}: raise ValueError("verdict")
    if not isinstance(value.get("reason"), str) or not value["reason"].strip(): raise ValueError("reason")
    findings = value.get("findings")
    if not isinstance(findings, list): raise ValueError("findings")
    for finding in findings:
        if not isinstance(finding, dict): raise ValueError("finding")
        for key in ("id", "severity", "file", "line", "note"):
            if key not in finding: raise ValueError(key)
        if finding["severity"] not in {"P0", "P1", "P2"}: raise ValueError("severity")
        if not isinstance(finding["line"], int) or isinstance(finding["line"], bool) or finding["line"] < 0: raise ValueError("line")
    print(value["verdict"])
except Exception as exc:
    print(f"INVALID:{exc}")
    sys.exit(1)
PY
)" || true
if [[ "$VALIDATION" == "PASS" ]]; then
  echo "[cc-auditor] JSON verdict PASS: $VERDICT_JSON" >&2
  exit 0
elif [[ "$VALIDATION" == "REJECT" ]]; then
  echo "[cc-auditor] JSON verdict REJECT: $VERDICT_JSON" >&2
  exit 2
fi
write_protocol_reject "JSON verdict 缺失或非法（claude 未产出合法 verdict）" 1
echo "[cc-auditor] JSON verdict 非法：${VALIDATION}" >&2
exit 2

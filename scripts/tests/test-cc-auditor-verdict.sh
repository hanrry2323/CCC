#!/bin/bash
# cc-auditor verdict 退出语义隔离测试；不访问真实业务仓或 Claude 服务。
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/cc-auditor-verdict.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

FAKE_CLAUDE="$TMP_DIR/fake-claude"
cat > "$FAKE_CLAUDE" <<'EOF'
#!/bin/bash
set -u
if [[ -n "${MOCK_VERDICT:-}" ]]; then
  printf '%s\n' "$MOCK_VERDICT" > "${MOCK_VERDICT_FILE:?}"
fi
printf '%s\n' "${MOCK_STDERR:-fake claude stderr}" >&2
exit "${MOCK_RC:-0}"
EOF
chmod +x "$FAKE_CLAUDE"

run_case() {
  local name="$1" expected_rc="$2" verdict="$3" claude_rc="$4"
  local log_dir="$TMP_DIR/$name"
  mkdir -p "$log_dir"
  printf '执行结果工件（测试隔离）\n' > "$log_dir/$name-ccc-result.md"

  set +e
  EXECUTOR_LOG_DIR="$log_dir" \
  CCC_BRAIN_CLAUDE_BIN="$FAKE_CLAUDE" \
  MOCK_VERDICT_FILE="$log_dir/$name-audit-verdict.md" \
  MOCK_VERDICT="$verdict" \
  MOCK_RC="$claude_rc" \
  bash "$ROOT/scripts/cc-auditor.sh" "$TMP_DIR/nonexistent-card.md" "$name" "__CCC_EMPTY__" \
    > "$log_dir/stdout.log" 2>&1
  local actual_rc=$?
  set -e

  if [[ "$actual_rc" -ne "$expected_rc" ]]; then
    printf 'FAIL %s: expected rc=%s, got rc=%s\n' "$name" "$expected_rc" "$actual_rc" >&2
    cat "$log_dir/stdout.log" >&2
    return 1
  fi
}

# Claude rc=1 但已写通过 verdict：按业务结论返回 0。
run_case pass 0 '机审：通过' 1
# Claude rc=1 但已写不通过 verdict：按业务结论返回 2。
run_case reject 2 '机审：不通过（mock reject）' 1
# 无 verdict 且 Claude rc=1：保留 stderr/stdout 诊断并返回 1。
run_case no-verdict 1 '' 1

printf 'cc-auditor verdict 退出语义测试全过\n'

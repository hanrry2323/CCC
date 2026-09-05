#!/bin/bash
# ── scripts/lib/result-report.sh ──
# C 阶段一：执行体结果旁路上报（可选、尽力而为）。
# 设计稿边界：只写独立事件存储，不碰卡文件 / card_gate / 状态机 / 机审 / 合入门禁；
# 文件链（log_dir 结果文件→引擎代写）仍是唯一事实源；上报失败不影响退出码与收单。
#
# 用法：
#   source scripts/lib/result-report.sh          # 定义 ccc_result_report
#   ccc_result_report <work_id> <dsh_rc> <duration_s> <log_dir>
#
# 行为：
#   - token 来自 CCC_RESULT_REPORT_TOKEN / CCC_RESULT_REPORT_URL（env 优先，回退 config.env）；
#     URL 缺省 http://192.168.3.116:7788/api/v1/board/result
#   - token 空 或 存在 <log_dir>/.result-report-disabled 旗标 → 跳过
#   - rc 0 → executor_completed；否则 executor_failed；payload 仅逻辑字段
#   - 403/404/503 → 写 disabled 旗标，本会话不再试
#   - 网络失败 → 仅 log_dir/<work_id>.result-report.log 一行备注，不改调用方 rc

ccc_result_report() {
  local work_id="$1" dsh_rc="$2" duration_s="$3" log_dir="$4"
  local token="" url="" cfg="" flag event body http rc_http
  token="${CCC_RESULT_REPORT_TOKEN:-}"
  url="${CCC_RESULT_REPORT_URL:-}"
  if [[ -z "$token" || -z "$url" ]]; then
    cfg="${CCC_CONFIG_ENV:-}"
    if [[ -n "$cfg" && -f "$cfg" ]]; then
      [[ -z "$token" ]] && token="$(grep -E '^CCC_RESULT_REPORT_TOKEN=' "$cfg" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)"
      [[ -z "$url" ]] && url="$(grep -E '^CCC_RESULT_REPORT_URL=' "$cfg" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)"
    fi
  fi
  url="${url:-http://192.168.3.116:7788/api/v1/board/result}"
  [[ -z "$token" ]] && return 0
  flag="${log_dir}/.result-report-disabled"
  [[ -f "$flag" ]] && return 0
  [[ -z "$log_dir" ]] && return 0

  local event="executor_failed"
  [[ "$dsh_rc" -eq 0 ]] && event="executor_completed"
  body="$(python3 - "$work_id" "$event" "$dsh_rc" "$duration_s" <<'PY'
import json, sys
work_id, event, rc, duration = sys.argv[1:5]
print(json.dumps({
    "work_id": work_id,
    "event": event,
    "payload": {
        "executor_rc": int(rc),
        "duration_s": int(duration),
        "result_path": f"{work_id}-ccc-result.md",
    },
}, separators=(",", ":")))
PY
)"
  rc_http="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' -X POST "$url" \
    -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
    --data-binary "$body" 2>/dev/null || printf '000')"
  case "$rc_http" in
    403|404|503)
      : > "$flag" 2>/dev/null || true
      ;;
    2??) ;;
    *)
      printf '[result-report] work=%s http=%s\n' "$work_id" "$rc_http" >> "${log_dir}/${work_id}.result-report.log" 2>/dev/null || true
      ;;
  esac
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  ccc_result_report "$@"
fi
#!/usr/bin/env bash
# ── scripts/test-evidence.sh ──
# 测试真实性机械截获（P0-1b · 2026-08-23）
#
# 用途：wrapper（dsh-executor.sh / dsh-auditor.sh）在 DSH 之外独立截获卡声明的
#       测试命令的真实 stdout/stderr + 退出码，写入独立证据日志（不经 DSH 加工）。
#       approve-merge.sh 合入时检查这份日志的真实退出码与测试框架输出，
#       不再信卡回写区 DSH 自述的「测试通过」文本。
#
# 用法：
#   scripts/test-evidence.sh <card_path> <workdir> <evidence_log>
#     card_path    任务卡绝对路径（解析 ## 门禁 节的 测试 命令）
#     workdir      测试命令执行的工作目录（卡 worktree / biz_worktree）
#     evidence_log 证据日志绝对路径（追加写入，含时间戳与退出码行）
#
# 退出码：0 = 卡无测试声明（无可验）或测试通过；非 0 = 测试命令真实失败。
# 调用方（auditor wrapper）在测试失败时以此硬打回，不让 DSH 跑机审。

set -uo pipefail

CARD_PATH="${1:?缺 card_path}"
WORKDIR="${2:?缺 workdir}"
EVIDENCE_LOG="${3:?缺 evidence_log}"

# 解析卡「## 门禁」节的 测试 命令（与 engine parse_gate_section 同源口径）。
TEST_CMD="$(python3 - "$CARD_PATH" <<'PY'
import sys
from pathlib import Path


def extract_command(payload: str) -> str:
    """Extract one Markdown inline-code command without touching shell syntax."""
    cmd = payload.strip()
    marker = chr(96)
    if not cmd.startswith(marker):
        return cmd

    # Only remove a leading Markdown code span pair.  A command without that
    # wrapper is returned unchanged, so legal shell backticks remain intact.
    delimiter_len = 1
    while delimiter_len < len(cmd) and cmd[delimiter_len] == marker:
        delimiter_len += 1
    delimiter = marker * delimiter_len
    closing = cmd.find(delimiter, delimiter_len)
    while closing != -1:
        suffix = cmd[closing + delimiter_len :].lstrip()
        if not suffix or suffix.startswith(("（", "(")):
            return cmd[delimiter_len:closing].strip()
        closing = cmd.find(delimiter, closing + delimiter_len)
    return cmd


p = Path(sys.argv[1])
if not p.is_file():
    sys.exit("")
lines = p.read_text(encoding="utf-8").splitlines()
in_gate = False
for line in lines:
    s = line.strip()
    if s.startswith("## 门禁"):
        in_gate = True
        continue
    if in_gate:
        if s.startswith("## ") or s.startswith("---"):
            break
        if s.startswith("测试") and (":" in s or "：" in s):
            # 全角冒号优先，避免 pytest 节点 ID 的 "::" 被腰斩。
            if "：" in s:
                payload = s.split("：", 1)[1]
            else:
                payload = s.split(":", 1)[1]
            print(extract_command(payload))
            break
PY
)"
if [[ -z "$TEST_CMD" ]]; then
  echo "no_test_declared" > "$EVIDENCE_LOG"
  exit 0
fi

mkdir -p "$(dirname "$EVIDENCE_LOG")"
{
  echo "=== test-evidence ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) card=$(basename "${CARD_PATH}") cmd=${TEST_CMD} workdir=${WORKDIR} ==="
} > "$EVIDENCE_LOG"

(
  cd "$WORKDIR" 2>/dev/null || exit 127
  eval "$TEST_CMD"
) >> "$EVIDENCE_LOG" 2>&1
RC=$?

{
  echo "=== exit_code=${RC} ==="
} >> "$EVIDENCE_LOG"

exit "$RC"

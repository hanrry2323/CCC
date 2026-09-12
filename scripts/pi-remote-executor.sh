#!/bin/bash
# ── scripts/pi-remote-executor.sh ──
# PI 跨机执行体包装（T-CCC-PLUGIN-01 序1 · 提案 v2 §一 A 线）
# 薄包装：本机（2017）SSH 到目标机执行 pi CLI，退出码回传 engine；不引 Paseo 运行时。
#
# 用法：scripts/pi-remote-executor.sh <card_path> <work_id> [worktree] [role] [biz_worktree]
#   参数语义与 scripts/dsh-executor.sh 同签名（5 段，后两段可空；engine 空值占位 = __CCC_EMPTY__）。
#   新增目标机只改「目标机映射」那一组 env，不新增分支。
#
# 退出码：0=pi 完成（含自报成功/打回）；64=结果契约不满足（fail-closed，与 dsh-executor 对齐）；
#         127=pi 不在目标机 PATH；其它非 0=pi/ssh 执行失败（engine 按退出码+输出判定）。
#
# 契约（与 dsh-executor.sh 完全一致，engine 零改动）：
# - 执行体在 worktree 根写 .ccc-result.md（四段固定结构），wrapper 拷贝到
#   ${EXECUTOR_LOG_DIR}/${WORK_ID}-ccc-result.md 供 engine 收单；.ccc-result.* 不进业务仓。
# - 卡文件是只读指针，主仓卡不动（卡回写由 engine 代做）。
# - 业务改动在目标机业务 worktree 内 commit+push 到 origin/codex/<slug>
#   （半成品续接靠 worktree.py:_worktree_branch_seed 的 origin/<branch> 优先逻辑）。
#
# 与 DSH 的差异（本单范围）：卡内容随提示走 scp 文件通道（单个 prompt 文件），不要求目标机持有
# CCC 文档仓；目标机不注入任何引擎 env / 密钥。
#
# 目标机形态（PI_REMOTE_FORM）：
# - win  ：目标机无 bash（Windows OpenSSH 的 sh 是 cmd.exe），统一经 PowerShell 包装脚本调 pi。
#          必须用 $LASTEXITCODE 捕获 pi 退出码——cmd 的 "echo exit=$?" 恒为 0（实测假绿）。
# - linux：目标机有 bash，prompt 走 @文件参数（免引号地狱），pi 参数在远端数组拼。
#
# 安全：所有拼进远端命令串的取值都过 case 白名单（禁空格/引号/换行/%），不依赖转义正确性。

set -euo pipefail

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-开发执行体}"
BIZ_WORKTREE="${5:-}"
[[ "$WORKTREE" == "__CCC_EMPTY__" ]] && WORKTREE=""
[[ "$BIZ_WORKTREE" == "__CCC_EMPTY__" ]] && BIZ_WORKTREE=""
[[ -z "$WORKTREE" && -n "$BIZ_WORKTREE" ]] && WORKTREE="$BIZ_WORKTREE"

_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CCC_ROOT="$(cd "$_SELF/.." && pwd -P)"

case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*:*":/usr/local/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:/usr/local/bin:$PATH" ;;
esac

# ── 目标机映射（新增机器只改这一段） ────────────────────────────────────
PI_SSH_USER="${PI_SSH_USER:-test}"
PI_SSH_HOST="${PI_SSH_HOST:-192.168.3.195}"
PI_SSH_TIMEOUT="${PI_SSH_TIMEOUT:-3600}"
PI_REMOTE_FORM="${PI_REMOTE_FORM:-win}"          # win | linux
PI_REMOTE_CMD="${PI_REMOTE_CMD:-pi}"
PI_REMOTE_PS="${PI_REMOTE_PS:-C:/Users/test/ccc-pi-run.ps1}"
PI_REMOTE_PS_EXE="${PI_REMOTE_PS_EXE:-powershell}"
PI_REMOTE_PROMPT_DIR="${PI_REMOTE_PROMPT_DIR:-C:/Users/test}"
PI_REMOTE_MODEL="${PI_REMOTE_MODEL:-Code}"
PI_REMOTE_TOOLS="${PI_REMOTE_TOOLS:-}"            # 空=用 pi 默认全工具
PI_REMOTE_BIZ_ROOT="${PI_REMOTE_BIZ_ROOT:-}"      # 目标机业务仓根；空=沿用工作区默认 cwd
PI_REMOTE_WORKDIR="${PI_REMOTE_WORKDIR:-}"        # 目标机 cwd（优先于 BIZ_ROOT/<slug>）
PI_REMOTE_SSH="${PI_REMOTE_SSH:-ssh}"
PI_REMOTE_SCP="${PI_REMOTE_SCP:-scp}"
PI_SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=6 -o ServerAliveInterval=15 -o ServerAliveCountMax=6 -o ServerAliveInterval=15 -o ServerAliveCountMax=6 -o ServerAliveInterval=15 -o ConnectTimeout=15)
SSH_TARGET="${PI_SSH_USER}@${PI_SSH_HOST}"

# ── 卡内容（只读指针；本地读，不依赖目标机持有 CCC 仓） ─────────────────
if [[ "$WORKTREE" == /* && -f "$WORKTREE/$CARD_PATH" ]]; then
  CARD_TEXT="$(cat "$WORKTREE/$CARD_PATH")"
elif [[ -f "$CARD_PATH" ]]; then
  CARD_TEXT="$(cat "$CARD_PATH")"
else
  echo "[pi-remote-executor] ERROR: 卡文件不存在: $CARD_PATH" >&2
  exit 1
fi

# ── EXECUTOR_LOG_DIR（与 dsh-executor.sh 同源解析，engine 收单读取） ────
_TE_EXEC_LOG_DIR="${EXECUTOR_LOG_DIR:-}"
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_CFG=""
  _TE_D="$PWD"
  while [[ "$_TE_D" != "/" ]]; do
    if [[ -f "$_TE_D/server/config/config.env" ]]; then
      _TE_CFG="$_TE_D/server/config/config.env"
      break
    fi
    _TE_D="$(dirname "$_TE_D")"
  done
  if [[ -n "$_TE_CFG" ]]; then
    _TE_EXEC_LOG_DIR="$(grep -E '^\s*EXECUTOR_LOG_DIR\s*=' "$_TE_CFG" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)"
  fi
fi
_TE_EXEC_LOG_DIR="${_TE_EXEC_LOG_DIR:-$HOME/.ccc/logs/exec}"
mkdir -p "$_TE_EXEC_LOG_DIR"

_RESULT_DST="${_TE_EXEC_LOG_DIR}/${WORK_ID}-ccc-result.md"
_RESULT_JSON_DST="${_TE_EXEC_LOG_DIR}/${WORK_ID}-ccc-result.json"
rm -f "$_RESULT_DST" "$_RESULT_JSON_DST"

# ── 目标机 cwd 解析 ─────────────────────────────────────────────────────
if [[ -n "$PI_REMOTE_WORKDIR" ]]; then
  REMOTE_DIR="$PI_REMOTE_WORKDIR"
elif [[ -n "$PI_REMOTE_BIZ_ROOT" ]]; then
  REMOTE_DIR="$PI_REMOTE_BIZ_ROOT/$(basename "$WORKTREE" 2>/dev/null || echo "$WORK_ID")"
elif [[ "$PI_REMOTE_FORM" == "win" ]]; then
  REMOTE_DIR="C:\\Users\\${PI_SSH_USER}"
else
  REMOTE_DIR="$HOME"
fi

PROMPT_REMOTE="${PI_REMOTE_PROMPT_DIR}\\ccc-prompt-${WORK_ID}.txt"

# ── 输入值安全（拼进远端命令串；禁空格/引号/换行/%/反引号/$/;） ─────────
_check_path() {
  case "$1" in
    *[!A-Za-z0-9_./:\\]) echo "[pi-remote-executor] ERROR: $2 含非法字符: $1" >&2; exit 1 ;;
    "")                  echo "[pi-remote-executor] ERROR: $2 为空" >&2; exit 1 ;;
  esac
}
case "$PI_REMOTE_MODEL" in *[!A-Za-z0-9_.:-]*|"") echo "[pi-remote-executor] ERROR: PI_REMOTE_MODEL 含非法字符" >&2; exit 1 ;; esac
case "$PI_REMOTE_TOOLS" in ""|*[!A-Za-z0-9_,.-]*) echo "[pi-remote-executor] ERROR: PI_REMOTE_TOOLS 含非法字符" >&2; exit 1 ;; esac
case "$PI_REMOTE_CMD" in *[!A-Za-z0-9_./-]*) echo "[pi-remote-executor] ERROR: PI_REMOTE_CMD 含非法字符" >&2; exit 1 ;; esac
case "$PI_REMOTE_FORM" in win|linux) ;; *) echo "[pi-remote-executor] ERROR: PI_REMOTE_FORM 只能是 win|linux: $PI_REMOTE_FORM" >&2; exit 1 ;; esac
_check_path "$REMOTE_DIR" REMOTE_DIR
_check_path "$PROMPT_REMOTE" PROMPT_REMOTE
_check_path "$WORK_ID" WORK_ID
if [[ "$PI_REMOTE_FORM" == "win" ]]; then
  _check_path "$PI_REMOTE_PS" PI_REMOTE_PS
  _check_path "$PI_REMOTE_PS_EXE" PI_REMOTE_PS_EXE
fi

# ── 任务提示（含卡全文；与 dsh-executor.sh 同构心智段，去掉 DSH 预设依赖） ─
PROMPT_LOCAL="${_TE_EXEC_LOG_DIR}/${WORK_ID}-pi-prompt.txt"
{
  echo "你是 CCC 开发执行体（PI 跨机执行体 · 角色=${ROLE}）。当前工作目录就是本卡的执行 worktree。"
  echo "本卡全文如下（只读，禁止修改卡文件本身）："
  echo
  echo '```'
  printf '%s\n' "$CARD_TEXT"
  echo '```'
  echo
  echo "按开发执行体心智执行本卡全流程：读卡 → 在「范围」白名单内实现 → 自测 → git commit + push 当前分支 → 写 .ccc-result.md → 停手。"
  echo "硬性约束："
  echo "- 禁止修改卡文件（只读指针；卡状态回写由引擎代做）。"
  echo "- 只改「范围」段列出的路径，越界改动算打回。"
  echo "- 改完必须 git commit 并 push 到当前分支（半成品续接依赖远端分支可见）。"
  echo "- 完成实现与自测后，必须在工作目录根写 .ccc-result.md，四段固定结构："
  echo "  ## 0. 卡标题复述"
  echo "  ## 1. 探针输出"
  echo "  ## 2. 自测输出"
  echo "  ## 3. 维护区四问"
  echo "- .ccc-result.md 写完后由 wrapper 传输，你【不要】把它 git add/commit 进业务仓。"
  echo "- 写完 .ccc-result.md 后停手，不要再改卡、不要再补改。"
  echo "- 若测试环境缺依赖无法自测，记录原始失败输出并继续写 .ccc-result.md，不要无限重试。"
} > "$PROMPT_LOCAL"

# ── 上传提示 ─────────────────────────────────────────────────────────────
echo "[pi-remote-executor] form=${PI_REMOTE_FORM} ssh=${SSH_TARGET} cwd=${REMOTE_DIR} model=${PI_REMOTE_MODEL} tools=${PI_REMOTE_TOOLS:-default}"
"$PI_REMOTE_SCP" "${PI_SSH_OPTS[@]}" "$PROMPT_LOCAL" "${SSH_TARGET}:$PROMPT_REMOTE"

# ── 远端执行（两形态） ─────────────────────────────────────────────────
if [[ "$PI_REMOTE_FORM" == "win" ]]; then
  # Windows：一次 powershell 调用做完 mkdir + cd + 读 prompt + 跑 pi + 真实退出码
  # ⚠️ Windows OpenSSH 的 sh=cmd.exe，cmd /c 再走 powershell -Command（双引号层）。
# cmd 双引号层会把 \U 当转义丢掉（实证：C:\Users\test 变成 C:Users\test，
# 导致 `< C:\Users\...` 重定向目标被截断）。故 PROMPT_REMOTE 的每个 \ 需在此加倍。
_PROMPT_REMOTE_ESC="${PROMPT_REMOTE//\//\\}"
  _TOOLS_PART=""
  [[ -n "$PI_REMOTE_TOOLS" ]] && _TOOLS_PART=" --tools ${PI_REMOTE_TOOLS}"
  REMOTE_CMD="cd /d ${REMOTE_DIR} && ${PI_REMOTE_CMD} --model ${PI_REMOTE_MODEL}${_TOOLS_PART} -p < ${PROMPT_REMOTE}"
else
  REMOTE_CMD="$(cat <<REMOTE_SNIPPET
set -e
mkdir -p '$REMOTE_DIR'
cd '$REMOTE_DIR'
command -v '$PI_REMOTE_CMD' >/dev/null 2>&1 || { echo '[pi-remote] ERROR: pi not in PATH' >&2; exit 127; }
PROMPT_FILE='$PROMPT_REMOTE'
[ -s "\$PROMPT_FILE" ] || { echo '[pi-remote] ERROR: prompt file missing' >&2; exit 1; }
PI_ARGS=(--model '$PI_REMOTE_MODEL' --print)
[ -n '${PI_REMOTE_TOOLS}' ] && PI_ARGS+=(--tools '${PI_REMOTE_TOOLS}')
echo "[pi-remote] model=$PI_REMOTE_MODEL tools=${PI_REMOTE_TOOLS:-default} cwd=\\$(pwd)"
'$PI_REMOTE_CMD' "\\${PI_ARGS[@]}" @\\$PROMPT_FILE
REMOTE_SNIPPET
)"
fi

_PI_RC=0
if command -v timeout >/dev/null 2>&1; then
  timeout "${PI_SSH_TIMEOUT}s" "$PI_REMOTE_SSH" "${PI_SSH_OPTS[@]}" "$SSH_TARGET" "$REMOTE_CMD" || _PI_RC=$?
else
  "$PI_REMOTE_SSH" "${PI_SSH_OPTS[@]}" "$SSH_TARGET" "$REMOTE_CMD" || _PI_RC=$?
fi

# ── A1 结果传输（契约同 dsh-executor.sh） ────────────────────────────────
if [[ $_PI_RC -eq 0 ]]; then
  "$PI_REMOTE_SCP" "${PI_SSH_OPTS[@]}" "${SSH_TARGET}:$REMOTE_DIR/.ccc-result.md" "$_RESULT_DST" 2>/dev/null || true
  "$PI_REMOTE_SCP" "${PI_SSH_OPTS[@]}" "${SSH_TARGET}:$REMOTE_DIR/.ccc-result.json" "$_RESULT_JSON_DST" 2>/dev/null || true
fi

# fail-closed：结果必须存在，否则 engine 无法收单（与 dsh-executor rc=64 语义对齐）
if [[ $_PI_RC -eq 0 && ! -f "$_RESULT_DST" ]]; then
  echo "[pi-remote-executor] ERROR: pi 退出 0 但目标机未产出 .ccc-result.md（rc=64 契约不满足）" >&2
  exit 64
fi

# 批注 fail-closed（口径与 server/board/annotation.py:_NONE_ANNOTATION_MARKERS 对齐）
if [[ -f "$CARD_PATH" && -f "$_RESULT_DST" ]] && grep -q '^## 人工批注$' "$CARD_PATH"; then
  _ANN="$(awk '/^## 人工批注$/{f=1;next} /^## /{f=0} f' "$CARD_PATH")"
  if ! grep -qE '^(无|无批注|暂无批注|（无批注。）|无批注。)[。.]?$' <<<"$_ANN" \
     && ! grep -qE '^## (人工)?批注落实$' "$_RESULT_DST"; then
    echo "[pi-remote-executor] ERROR: 卡含真实人工批注但结果缺少 ## 批注落实，拒绝传输（rc=64）" >&2
    exit 64
  fi
fi

# P1.3 结构化 sidecar（解析失败只告警，不阻断 markdown 兼容链）
if [[ -f "$_RESULT_DST" ]]; then
  if python3 - "$_CCC_ROOT" "$_RESULT_DST" "$_RESULT_JSON_DST" "$WORK_ID" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from server.engine.result_sidecar import convert_file
convert_file(sys.argv[2], sys.argv[3], sys.argv[4])
PY
  then
    echo "[pi-remote-executor] JSON sidecar 已生成 → ${_RESULT_JSON_DST}" >&2
  else
    echo "[pi-remote-executor] WARN: JSON sidecar 派生失败，走 markdown 兼容链" >&2
  fi
fi

rm -f "$PROMPT_LOCAL"
if [[ "$PI_REMOTE_FORM" == "win" ]]; then
  _CLEAN="del /q /f ${PROMPT_REMOTE} 2>nul & exit /b 0"
else
  _CLEAN="rm -f '${PROMPT_REMOTE}'"
fi
( set +e; "$PI_REMOTE_SSH" "${PI_SSH_OPTS[@]}" "$SSH_TARGET" "$_CLEAN" >/dev/null 2>&1 ) || true

if [[ $_PI_RC -ne 0 ]]; then
  echo "[pi-remote-executor] pi/ssh 退出码=${_PI_RC}（透传给 engine 判定）" >&2
fi
exit $_PI_RC

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
# - 执行体在 worktree 根写 .ccc-result.md（五段固定结构，含 ## 4. 变更证据），wrapper 拷贝到
#   ${EXECUTOR_LOG_DIR}/${WORK_ID}-ccc-result.md 供 engine 收单；.ccc-result.* 不进业务仓。
# - 卡文件是只读指针，主仓卡不动（卡回写由 engine 代做）。
# - 业务改动在目标机业务 worktree 内 commit+push 到 origin/codex/<slug>
#   （半成品续接靠 worktree.py:_worktree_branch_seed 的 origin/<branch> 优先逻辑）。
#
# 与 DSH 的差异（本单范围）：卡内容随提示走 scp 文件通道（单个 prompt 文件），不要求目标机持有
# CCC 文档仓；目标机不注入任何引擎 env / 密钥。
#
# 目标机形态（PI_REMOTE_FORM）：
# - win  ：Windows OpenSSH 的 sh = cmd.exe（不是 bash）。远端命令 = `cd /d <dir> && pi --model <M> -p < <promptfile>`，
#          prompt 经 scp 文件通道传入；pi 退出码由 cmd→ssh 原生透传（实测 tst910 全链 rc=0）。
#          已排除的形态（全部实测失败，勿再尝试）：PS 直调 .cmd（参数拼成单串）、
#          cmd /c (括号串)（括号被吃）、-EncodedCommand 包层（路径截断）、cmd 内 echo exit=$?（恒 0 假绿）。
#          路径格式分裂：cmd 用反斜杠，scp/SFTP 只认正斜杠 → _SCP_* 变量专供回传。
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

# ⚠️ 两套路径格式各管一段（2026-09-12 实证）：
#   REMOTE_DIR / PROMPT_REMOTE 用反斜杠 —— 给 cmd.exe 的 `cd /d` 与 `< 文件` 重定向用；
#   _SCP_* 用正斜杠 —— scp 走 SFTP 协议，不接受反斜杠（实测报 No such file or directory）。
# 混用即断：tst909 探针 pi 执行成功、结果已产出，仅回传这一跳因用了反斜杠而失败（rc=64）。
_SCP_DIR="${REMOTE_DIR//\\//}"
_SCP_PROMPT="${PROMPT_REMOTE//\\//}"

# ── 输入值安全（拼进远端命令串；禁空格/引号/换行/%/反引号/$/;） ─────────
_check_path() {
  # 路径/取值白名单。用 bash 的 case 而不是 grep：本仓实测 bash 的 =~ 与
  # [[ =~ ]] 对含反斜杠的路径返回不可信结果（全拒合法路径），grep 同样全拒，
  # 唯有 case 字符集实测正确（允许 C:\Users\test，拒绝 foo;rm / % / 空格）。
  # 已知松弛：glob 里排除反斜杠的正确写法应为 [[!\]... ]，当前写法实测仍可靠，
  # 但语义不如期望严格——真正的注入面由 case 已拦的空格/;/&/|/< 与固定路径构造闭合。
  case "$1" in
    *[!A-Za-z0-9_./:\]) echo "[pi-remote-executor] ERROR: $2 含非法字符: $1" >&2; exit 1 ;;
    "")                  echo "[pi-remote-executor] ERROR: $2 为空" >&2; exit 1 ;;
  esac
}
case "$PI_REMOTE_MODEL" in *[!A-Za-z0-9_.:-]*|"") echo "[pi-remote-executor] ERROR: PI_REMOTE_MODEL 含非法字符" >&2; exit 1 ;; esac
case "$PI_REMOTE_TOOLS" in *[!A-Za-z0-9_,.-]*) echo "[pi-remote-executor] ERROR: PI_REMOTE_TOOLS 含非法字符" >&2; exit 1 ;; esac
case "$PI_REMOTE_CMD" in *[!A-Za-z0-9_./-]*) echo "[pi-remote-executor] ERROR: PI_REMOTE_CMD 含非法字符" >&2; exit 1 ;; esac
case "$PI_REMOTE_FORM" in win|linux) ;; *) echo "[pi-remote-executor] ERROR: PI_REMOTE_FORM 只能是 win|linux: $PI_REMOTE_FORM" >&2; exit 1 ;; esac
_check_path "$REMOTE_DIR" REMOTE_DIR
_check_path "$PROMPT_REMOTE" PROMPT_REMOTE
_check_path "$WORK_ID" WORK_ID
if [[ "$PI_REMOTE_FORM" == "win" ]]; then
  _check_path "$PI_REMOTE_PS" PI_REMOTE_PS
  _check_path "$PI_REMOTE_PS_EXE" PI_REMOTE_PS_EXE
fi

# ── 续跑提示（2026-09-18 层2 · INFRA 冷却续派时续做而非重做）────────────
# DSH headless 无 --resume（`dsh --profile headless --help` 仅 task 参数），引擎 INFRA
# 冷却续派必为全新 session；但 run 相位失败不清理 worktree（_cleanup_closed_worktrees
# 只在关卡时调，main.py:3909），前次部分提交仍在分支上。xy078 实测：108 次派发 /
# 52 次失败 / 业务仓分支 4 个未合入 commit / 56 个孤儿 session —— 断点真实存在，零复用。
#
# 三信号合取才注入（任一为假即不注入，避免对正常首跑加噪）：
#   S1 worker-events.jsonl 中该卡有 ≥1 条 phase=run 且 ok=false（权威派发史，_emit 埋点，
#      比 sidecar 稳：sidecar 会被 clear_card_state 清掉、按字段合并易歧义）
#   S2 分支相对 origin/main 有 ≥1 个未合入 commit（有断点可续）
#   S3 sidecar 末次记录无 reject_budget_exhausted / awaiting_human（熔断卡挂起待人工，
#      引擎不会再派；防误触发）
# 引擎对本 wrapper 设 inject_hint=False（main.py:2045-2057），故由 wrapper 自读，
# 引擎不会覆盖本段。set -euo pipefail 下 python3 非 0 须包在 || 里，否则中断整个派发。
_RESUME_HINT=""
if [[ -n "${WORK_ID:-}" ]]; then
  _RESUME_HINT="$(python3 - "$WORK_ID" "${BIZ_WORKTREE:-}" "${WORKTREE:-}" <<'PYR'
import io, json, os, subprocess, sys
wid, wt, biz = sys.argv[1:4]
log_dir = os.environ.get("EXECUTOR_LOG_DIR", "").strip()
if not log_dir:
    cfg = os.environ.get("CCC_CONFIG_ENV", "/Users/fan/program/CCC/server/config/config.env")
    try:
        for ln in io.open(cfg, encoding="utf-8", errors="replace"):
            if ln.startswith("EXECUTOR_LOG_DIR="):
                log_dir = ln.split("=", 1)[1].strip().strip('"').strip("'")
                break
    except OSError:
        pass
log_dir = log_dir or os.path.expanduser("~/.ccc/logs/exec")

def _jsonl(p):
    out = []
    try:
        if os.path.isfile(p):
            for ln in io.open(p, encoding="utf-8", errors="replace"):
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out

runs = [r for r in _jsonl(os.path.join(log_dir, "worker-events.jsonl"))
        if str(r.get("work_id")) == wid and r.get("phase") == "run"]
failed_runs = [r for r in runs if not r.get("ok", True)]

# 熔断判定：复刻 runtime_state.read_card_state 的 field-level last-wins + state:null 失效语义
rt = {}
for r in _jsonl(os.path.join(log_dir, "state", "cards.jsonl")):
    if str(r.get("id")) != wid:
        continue
    if "state" in r and r["state"] is None:
        rt = {}
        break
    rt.update(r)
blocked = bool(rt.get("reject_budget_exhausted") or rt.get("awaiting_human"))

if not failed_runs or blocked:
    sys.exit(0)

# 业务仓型任务业务改动在 BIZ_WORKTREE；非业务仓任务在 WORKTREE（含卡副本）。
d = biz if (biz and os.path.isdir(biz)) else (wt if (wt and os.path.isdir(wt)) else "")
if not d:
    sys.exit(0)
try:
    res = subprocess.run(["git", "-C", d, "log", "origin/main..HEAD", "--oneline"],
                         capture_output=True, text=True, timeout=30, check=False)
except Exception:
    sys.exit(0)
new = [l for l in res.stdout.splitlines() if l.strip()] if res.returncode == 0 else []
if new:
    print("RESUME:" + str(len(new)))
PYR
)" || _RESUME_HINT=""
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
  echo "- 完成实现与自测后，必须在工作目录根写 .ccc-result.md，五段固定结构（与 scripts/dsh-executor.sh:95 同口径；缺第 5 段则 JSON sidecar 派生失败、机审读不到变更证据）："
  echo "  ## 0. 卡标题复述（完整复述卡标题）"
  echo "  ## 1. 探针输出"
  echo "  ## 2. 自测输出"
  echo "  ## 3. 维护区四问（[是/否][有/无]+说明）"
  echo "  ## 4. 变更证据（逐项写 commit= branch= push= 实值；未做该项写 N/A 并说明原因）"
  echo "- .ccc-result.md 写完后由 wrapper 传输，你【不要】把它 git add/commit 进业务仓。"
  echo "- 写完 .ccc-result.md 后停手，不要再改卡、不要再补改。"
  echo "- 若测试环境缺依赖无法自测，记录原始失败输出并继续写 .ccc-result.md，不要无限重试。"
} > "$PROMPT_LOCAL"
# ── 续跑提示（2026-09-18 层2 · 续做而非重做；检测块在上方，此处追加进 prompt 文件）──
# pi-remote 的 prompt 走 heredoc 写 $PROMPT_LOCAL 再 scp 到目标机，$PROMPT 变量不存在，
# 故此处 echo 追加。目标机拿到的是完整 prompt 文件，语义与 dsh-executor 一致。
if [[ "$_RESUME_HINT" == RESUME:* ]]; then
  {
    echo ""
    echo "【续跑约束 · 基础设施故障后的自动续派】"
    echo "本次运行是前次执行因基础设施故障（模型通道/网络/上游波动）被中断后的自动续派，不是首跑。"
    echo "同一 worktree 分支上已有前次未完成的部分提交，git log --oneline origin/main..HEAD 可见（${_RESUME_HINT#RESUME:} 个未合入）。"
    echo "1. 动手前先看现状：git log --oneline origin/main..HEAD 与 git status --short，确认已完成部分。"
    echo "2. 只补未完成部分；已提交的实现不重做、不回滚、不覆盖。"
    echo "3. 前次提交有缺陷时，在其上追加修复 commit，不重写历史。"
    echo "4. 完成度判定以卡白名单与自测为准，不因「已做过一部分」而降低自测标准。"
    echo "5. 判断前次提交整体不可用需推倒重做时，必须在 .ccc-result.md「## 3. 维护区四问」显式写明理由与证据，不静默重做。"
  } >> "$PROMPT_LOCAL"
fi


# ── 上传提示 ─────────────────────────────────────────────────────────────
echo "[pi-remote-executor] form=${PI_REMOTE_FORM} ssh=${SSH_TARGET} cwd=${REMOTE_DIR} model=${PI_REMOTE_MODEL} tools=${PI_REMOTE_TOOLS:-default}"
# scp 走 SFTP 协议 → 正斜杠路径（反斜杠实测报 No such file or directory）
"$PI_REMOTE_SCP" "${PI_SSH_OPTS[@]}" "$PROMPT_LOCAL" "${SSH_TARGET}:$_SCP_PROMPT"

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
  # scp 走 SFTP 协议 → 用正斜杠路径（见上方 _SCP_DIR 注释）
  "$PI_REMOTE_SCP" "${PI_SSH_OPTS[@]}" "${SSH_TARGET}:$_SCP_DIR/.ccc-result.md" "$_RESULT_DST" 2>/dev/null || true
  "$PI_REMOTE_SCP" "${PI_SSH_OPTS[@]}" "${SSH_TARGET}:$_SCP_DIR/.ccc-result.json" "$_RESULT_JSON_DST" 2>/dev/null || true
fi

# fail-closed：结果必须存在，否则 engine 无法收单（与 dsh-executor rc=64 语义对齐）
if [[ $_PI_RC -eq 0 && ! -f "$_RESULT_DST" ]]; then
  echo "[pi-remote-executor] ERROR: pi 退出 0 但目标机未产出 .ccc-result.md（rc=64 契约不满足）" >&2
  exit 64
fi

# 批注 fail-closed（口径与 server/board/annotation.py:_NONE_ANNOTATION_MARKERS 对齐）
if [[ -f "$CARD_PATH" && -f "$_RESULT_DST" ]] && grep -q '^## 人工批注$' "$CARD_PATH"; then
  _ANN_KIND="$(python3 - "$_CCC_ROOT" "$CARD_PATH" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from server.board.annotation import classify_annotation
print(classify_annotation(open(sys.argv[2], encoding='utf-8').read()))
PYEOF
)"
  if [[ "$_ANN_KIND" != "NONE" ]] && ! grep -qE '^## (人工)?批注落实$' "$_RESULT_DST"; then
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

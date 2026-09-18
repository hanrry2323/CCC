#!/bin/bash
# ── scripts/dsh-executor.sh ──
# DSH 开发执行体包装（S3 · CCC×DSH 整合；2026-08-23 指令A 入编改造）
# 心智来自预设 ~/.dsh/.agent-presets/dsh-executor（--patch 直挂 headless），
# 本 wrapper 只传「卡指针 + 运行参数 + 授权声明」——预设管心智，卡管任务。
#
# 用法：
#   scripts/dsh-executor.sh <card_path> <work_id> <worktree> [role] [biz_worktree]
#
# biz_worktree（P1-b 2026-08-23）：业务仓型任务每卡独立 worktree；非业务仓任务传空，
# 此时忽略。业务仓型任务 cwd 切 biz_worktree（业务仓内改动），card_path 仍为绝对路径。
#
# 退出码：0=DSH 完成（含自报成功/打回）；非0=执行失败。engine 按退出码+输出判定。
# 前置：2017 已配 OPENCODE_GO_API_KEY（com.ccc.engine.plist env）+ DSH 0.1.1-rc.2。

set -euo pipefail
# P1-d/rebuild-phase2 + P0-1：密钥单源 + 三态预检（非 0 一律阻断，保留真实退出码）
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CCC_ROOT="$(cd "$_SELF/.." && pwd -P)"
# shellcheck source=scripts/dsh-key.sh
source "$_SELF/dsh-key.sh" 2>/dev/null || true
# F7（2026-09-18）：set -u 下的前置引用竞态硬化。旧写法
#   _KC_RC=0
#   "$_SELF/dsh-key-check.sh" --quiet || _KC_RC=$?
# 在 macOS 默认 bash 3.2（/bin/bash）下，当 key-check 非 0 返回（2/3/5/6 等）时会在
# 后续 `[[ $_KC_RC -ne 0 ]]` / `exit "$_KC_RC"` 误报 `_KC_RC: unbound variable`
#（F5 窗 run2 实证 `_KC_RC: unbound variable` 崩溃，派发整体中断）。
# 实测根因：bash 3.2 在 `set -u` 生效时，对「捕获 $?」得到的变量名在 if/exit/echo
# 中的多次引用会错位（同块内首次引用后可见、二次引用即被判 unbound）。
# 修复：捕获期间临时 `set +e +u`（关闭 errexit + nounset），恢复 `set -e -u`；
# 并在 if 体首行把退出码一次性拷贝到 `_KC_EXIT`，后续只引用 `_KC_EXIT`，
# 既绕开解析 bug，又完整保留三态退出码（2=QUOTA / 3=AUTH / 5=PROBE / 6=NO_KEY），
# 非 0 一律阻断（保留真实退出码，引擎按码区分 QUOTA/AUTH/PROBE/NO_KEY）。
_KC_RC=0
set +e +u
"$_SELF/dsh-key-check.sh" --quiet
_KC_RC=$?
set -e -u
if [[ $_KC_RC -ne 0 ]]; then
  _KC_EXIT=$_KC_RC
  echo "[FATAL] DSH gateway precheck failed (code=$_KC_EXIT); no execution" >&2
  exit "$_KC_EXIT"
fi

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-开发执行体}"
BIZ_WORKTREE="${5:-}"
# build_command uses a sentinel to preserve empty optional argv positions.
[[ "$WORKTREE" == "__CCC_EMPTY__" ]] && WORKTREE=""
[[ "$BIZ_WORKTREE" == "__CCC_EMPTY__" ]] && BIZ_WORKTREE=""

# R-2026-08-23 P0-2：launchd 下 Engine PATH 极简（/usr/bin:/bin:/usr/sbin:/sbin），
# 裸 `dsh` 会 127。兜底补 npm 全局 bin（dsh 本体）+ /usr/local/bin（node，dsh 运行时入口），
# 仍找不到就明确报错（不静默）。P0-2b 补充：仅补 dsh 目录不够，node 缺失同样 rc=127。
case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*:*":/usr/local/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:/usr/local/bin:$PATH" ;;
esac
command -v dsh >/dev/null 2>&1 || { echo "[dsh-executor] ERROR: dsh 不在 PATH（已尝试 \$HOME/.npm-global/bin）" >&2; exit 127; }
command -v node >/dev/null 2>&1 || { echo "[dsh-executor] ERROR: node 不在 PATH（DSH 运行时需要，已尝试 /usr/local/bin）" >&2; exit 127; }

# R-2026-08-23 P0-3：worktree 的 git 元数据在主仓 .git（cwd 之外），默认
# workspace-write 沙箱会拒绝 commit 且 headless 无审批通道 → 执行体无法收口。
# 与生产 harness 同款语义：danger-full-access + approval never。
export DSH_PERMISSION_MODE="${DSH_PERMISSION_MODE:-danger-full-access}"

# 预设心智（入编）：缺失即明确失败，不静默降级为无心智裸跑
PRESET="$HOME/.dsh/.agent-presets/dsh-executor/agent.cordis.yml"
[ -f "$PRESET" ] || { echo "[dsh-executor] ERROR: 执行体预设缺失: $PRESET" >&2; exit 3; }

# 从预设提取 persona → 生成 headless system-prompt 槽位 overlay
# （--patch 的 id 是组合树槽位；预设文件本身是插件行列表，需派生而非直挂）
OVL_DIR="$(mktemp -d)"
OVERLAY="$OVL_DIR/overlay.yml"
python3 - "$PRESET" "$OVERLAY" <<'PY'
import sys, yaml
rows = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
persona = next(r["config"]["text"] for r in rows if r.get("id") == "persona")
yaml.safe_dump(
    [{"id": "system-prompt", "config": {"persona": persona}}],
    open(sys.argv[2], "w", encoding="utf-8"),
    allow_unicode=True,
)
PY

# 切工作目录：业务仓型任务优先 biz_worktree（业务仓内改动），否则 worktree（含卡副本）
# P1-b 2026-08-23：biz_worktree 存在时业务仓为唯一工作区，cwd 必须落在其中。
if [ -n "$BIZ_WORKTREE" ] && [ -d "$BIZ_WORKTREE" ]; then
  cd "$BIZ_WORKTREE"
  WORKDIR_LABEL="biz_worktree"
elif [ -n "$WORKTREE" ] && [ -d "$WORKTREE" ]; then
  cd "$WORKTREE"
  WORKDIR_LABEL="worktree"
else
  WORKDIR_LABEL="cwd"
fi

PROMPT="任务卡：${CARD_PATH}（work ${WORK_ID}，角色：${ROLE}）。
按你的开发执行体心智执行本卡全流程（读卡→白名单实现→自测→worktree commit+push→写 .ccc-result.md→停手）。
授权声明：本次运行授权在 ${WORKDIR_LABEL} $(pwd) 内读写卡白名单文件并执行 git add/commit/push（限卡白名单范围）。
工作目录：$(pwd)
权限约束：当前会话已由 wrapper 预先授予 danger-full-access。工具调用不得再传 sandbox_permissions，不得请求权限升级，也不得把 danger-full-access 作为重复升级参数；直接在当前已授予权限下执行命令。若工具 schema 要求权限字段，省略该字段或使用当前已授予上下文，不要发起 escalation。
测试约束：测试环境缺少 pytest 时，优先使用业务仓已有入口或解释器；不要调用带 danger-full-access escalation 参数的 uvx/临时环境安装命令。确实无法测试时，记录原始失败并继续写 .ccc-result.md，不要无限重试。

【严格约束 · A1 结果契约】
- 禁止修改主仓卡文件 ${CARD_PATH}（那是只读指针；卡回写由引擎代做）。
- 完成实现与自测后，必须在 worktree 根写 .ccc-result.md，结构固定：
  # 执行结果 · <work_id> · <卡标题>
  四段：## 0. 卡标题复述（完整复述卡标题）/ ## 1. 探针输出 / ## 2. 自测输出 / ## 3. 维护区四问（[是/否][有/无]+说明）/ ## 4. 变更证据（commit= branch= push=）
- 若任务卡包含「## 人工批注」且批注非「无批注」占位，必须额外输出 `## 批注落实` 段，逐条引用批注并说明已落实/未落实及证据；不得写「无批注」或省略该段。
- .ccc-result.md 写完后由 wrapper 负责传输，你【不要】把它 git add/commit 进业务仓。
- 写完 .ccc-result.md 后停手，不要再改卡。"

# ccc073（2026-08-24）：业务仓型任务 cwd 落在 biz_worktree，卡文件不在眼前——
# xy059 首轮实证执行体普遍漏做文档仓侧卡回写。BIZ_WORKTREE 非空时 PROMPT 追加
# 双仓语义提示；WORKTREE 缺失时文案引用空路径会产生误导，故同样不加。
# 仅增补提示文案，其余零逻辑变化。
if [ -n "$BIZ_WORKTREE" ] && [ -n "$WORKTREE" ]; then
  PROMPT+="
双仓提示：本卡文件位于文档仓分支副本 ${WORKTREE}/ 下（相对路径 ${CARD_PATH#$_CCC_ROOT/}）。业务改动在当前目录实施；卡文件的状态回写、回写区与维护区四问必须在文档仓 worktree 的卡副本上完成并 commit+push 到同一分支；主仓 ${CARD_PATH} 只读勿动。"
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

if [[ "$_RESUME_HINT" == RESUME:* ]]; then
  PROMPT+="

【续跑约束 · 基础设施故障后的自动续派】
本次运行是前次执行因基础设施故障（模型通道/网络/上游波动）被中断后的自动续派，不是首跑。
同一 worktree 分支上已有前次未完成的部分提交，git log --oneline origin/main..HEAD 可见（${_RESUME_HINT#RESUME:} 个未合入）。
1. 动手前先看现状：git log --oneline origin/main..HEAD 与 git status --short，确认已完成部分。
2. 只补未完成部分；已提交的实现不重做、不回滚、不覆盖。
3. 前次提交有缺陷时，在其上追加修复 commit，不重写历史。
4. 完成度判定以卡白名单与自测为准，不因「已做过一部分」而降低自测标准。
5. 判断前次提交整体不可用需推倒重做时，必须在 .ccc-result.md「## 3. 维护区四问」显式写明理由与证据，不静默重做。"
fi
# 后台执行 + wait 传播退出码（R1）；engine 侧另有全局超时
_REPORT_STARTED_AT="$(date +%s)"
dsh --profile headless --patch "$OVERLAY" "$PROMPT" &
PID=$!
DSH_RC=0
wait "$PID" || DSH_RC=$?
rm -f "$OVERLAY"

# P0-1b 测试真实性机械截获（2026-08-23）：DSH 之外独立跑卡门禁测试并落证据日志。
# 日志落 $EXECUTOR_LOG_DIR/<work_id>.test-evidence.log（与 Engine 同源，不经 DSH 加工）。
_TE_EXEC_LOG_DIR="${EXECUTOR_LOG_DIR:-}"
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_CFG="${CCC_CONFIG_ENV:-$_CCC_ROOT/server/config/config.env}"
  if [[ -f "$_TE_CFG" ]]; then
    _TE_EXEC_LOG_DIR="$(grep -E '^\s*EXECUTOR_LOG_DIR\s*=' "$_TE_CFG" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\"' | tr -d "'" | xargs 2>/dev/null || true)"
  fi
fi
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_EXEC_LOG_DIR="$HOME/.ccc/logs/exec"
fi
_TE_EVIDENCE_LOG="${_TE_EXEC_LOG_DIR}/${WORK_ID}.test-evidence.log"
# 证据 workdir：优先 biz_worktree，其次 worktree，其次当前目录（已 cd 过）
_TE_EVIDENCE_WORKDIR=""
if [[ -n "${BIZ_WORKTREE:-}" && -d "$BIZ_WORKTREE" ]]; then
  _TE_EVIDENCE_WORKDIR="$BIZ_WORKTREE"
elif [[ -n "${WORKTREE:-}" && -d "$WORKTREE" ]]; then
  _TE_EVIDENCE_WORKDIR="$WORKTREE"
else
  _TE_EVIDENCE_WORKDIR="$(pwd)"
fi
if [[ -f "$CARD_PATH" && -d "$_TE_EVIDENCE_WORKDIR" ]]; then
  bash "$_CCC_ROOT/scripts/test-evidence.sh" "$CARD_PATH" "$_TE_EVIDENCE_WORKDIR" "$_TE_EVIDENCE_LOG" || true
  echo "[dsh-executor] 测试证据已截获 → ${_TE_EVIDENCE_LOG}" >&2
fi

# ── A1 结果传输（2026-09-03）：DSH 在 worktree 写 .ccc-result.md，wrapper 拷贝到 log_dir ──
# worktree 会被引擎回收清理，结果必须落到 log_dir/<work_id>-ccc-result.md 供引擎收单读取。
# .ccc-result.md 不 commit 进业务仓（防污染 mx/hp 真业务仓），传输只走本 log_dir 通道。
_RESULT_SRC="$(pwd)/.ccc-result.md"
_RESULT_JSON_SRC="$(pwd)/.ccc-result.json"
_RESULT_DST="${_TE_EXEC_LOG_DIR}/${WORK_ID}-ccc-result.md"
_RESULT_JSON_DST="${_TE_EXEC_LOG_DIR}/${WORK_ID}-ccc-result.json"

# A1 fail-closed：卡含真实人工批注时，结果必须给出 ## 批注落实，否则拒绝传输（rc=64）。
# 「无批注」白名单与 server/board/annotation.py:_NONE_ANNOTATION_MARKERS 对齐
# （2026-09-10 xy067 三轮 rc=64 实证：卡批注=「无」被旧 grep 误判为真实批注）。
if [[ -f "$CARD_PATH" && -f "$_RESULT_SRC" ]]; then
  if grep -q '^## 人工批注$' "$CARD_PATH"; then
    _ANN_KIND="$(python3 - "$_CCC_ROOT" "$CARD_PATH" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from server.board.annotation import classify_annotation
print(classify_annotation(open(sys.argv[2], encoding='utf-8').read()))
PYEOF
)"
    if [[ "$_ANN_KIND" != "NONE" ]] && ! grep -qE '^## (人工)?批注落实$' "$_RESULT_SRC"; then
      echo "[dsh-executor] ERROR: 卡含真实人工批注但结果缺少 ## 批注落实，拒绝传输（rc=64）" >&2
      exit 64
    fi
  fi
fi
if [[ "$DSH_RC" -eq 0 ]]; then
  if [[ -f "$_RESULT_SRC" ]]; then
    # P1.3：从既有四段 markdown 派生结构化 sidecar。解析失败只告警，不能阻断
    # markdown 兼容链；sidecar 不进入业务仓，仅随结果通道传输。
    if python3 - "$_CCC_ROOT" "$_RESULT_SRC" "$_RESULT_JSON_SRC" "$WORK_ID" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from server.engine.result_sidecar import convert_file
convert_file(sys.argv[2], sys.argv[3], sys.argv[4])
PY
    then
      echo "[dsh-executor] JSON sidecar 已生成 → ${_RESULT_JSON_SRC}" >&2
    else
      echo "[dsh-executor] WARN: JSON sidecar 生成失败，保留 markdown 结果链" >&2
      rm -f "$_RESULT_JSON_SRC"
    fi
    if cp "$_RESULT_SRC" "$_RESULT_DST" 2>/dev/null; then
      echo "[dsh-executor] 结果文件已传输 → ${_RESULT_DST}" >&2
      if [[ -f "$_RESULT_JSON_SRC" ]] && cp "$_RESULT_JSON_SRC" "$_RESULT_JSON_DST" 2>/dev/null; then
        echo "[dsh-executor] JSON sidecar 已传输 → ${_RESULT_JSON_DST}" >&2
      elif [[ -f "$_RESULT_JSON_SRC" ]]; then
        echo "[dsh-executor] WARN: JSON sidecar 拷贝失败，回退 markdown" >&2
        rm -f "$_RESULT_JSON_DST"
      fi
    else
      echo "[dsh-executor] ERROR: 结果文件拷贝失败 ${_RESULT_SRC} → ${_RESULT_DST}" >&2
      exit 64
    fi
  else
    # F7（2026-09-18）：退出码 0 但信封缺失 = 明确失败，rc=64 语义保留，但必须
    # 落一行可 grep 的死因 + 贴 DSH 会话尾 30 行做现场留存。F5 窗诊断实证：
    # run3/4/6/7「DSH 退出码 0 但 .ccc-result.md 缺失 → 上报 rc=64」空转，此前
    # 只 echo 一句 WARN 就 exit，无从判定 DSH 到底做了什么/停在哪步——xy079 连烧
    # 多轮全死于此，只能靠人工翻 DSH 会话还原。
    # stderr → engine 重定向进 ${WORK_ID}.log（ENVELOPE_MISSING 死因可 grep）；
    # 会话尾另落独立文件，避免与 engine 持句柄的 .log 双写产生偏移错乱。
    _SESSION_LOG="${_TE_EXEC_LOG_DIR}/${WORK_ID}.log"
    _ENV_MISS_LOG="${_TE_EXEC_LOG_DIR}/${WORK_ID}-envelope-missing.log"
    mkdir -p "$_TE_EXEC_LOG_DIR" 2>/dev/null || true
    echo "[dsh-executor] ENVELOPE_MISSING work=${WORK_ID}：DSH 退出码 0 但信封缺失（${_RESULT_SRC} 不存在），上报 rc=64" >&2
    {
      echo "[dsh-executor] ENVELOPE_MISSING work=${WORK_ID} dsh_rc=${DSH_RC} cwd=$(pwd) src=${_RESULT_SRC}"
      echo "[dsh-executor] 信封查找路径不存在；cwd 内容（前 20 行）:"
      ls -la --time-style=+%H:%M:%S 2>/dev/null | head -20 || ls -l | head -20
      echo "[dsh-executor] DSH 会话尾 30 行（现场留存，日志=${_SESSION_LOG}）:"
      if [[ -f "$_SESSION_LOG" ]]; then
        tail -30 "$_SESSION_LOG"
      else
        echo "[dsh-executor] （会话日志不存在：${_SESSION_LOG}）"
      fi
    } > "$_ENV_MISS_LOG" 2>/dev/null || true
    echo "[dsh-executor] 现场已留存 → ${_ENV_MISS_LOG}" >&2
    exit 64
  fi
fi

# C 阶段一：可选旁路上报。独立于文件链，失败不改变 DSH rc。
# shellcheck source=scripts/lib/result-report.sh
source "$_SELF/lib/result-report.sh"
_REPORT_DURATION=$(( $(date +%s) - _REPORT_STARTED_AT ))
ccc_result_report "$WORK_ID" "$DSH_RC" "$_REPORT_DURATION" "$_TE_EXEC_LOG_DIR" || true

echo "[dsh-executor] work=${WORK_ID} 执行结束 rc=${DSH_RC}"
exit "$DSH_RC"

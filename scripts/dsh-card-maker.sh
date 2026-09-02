#!/bin/bash
# ── scripts/dsh-card-maker.sh ──
# CCC 出卡 Agent 入口（2026-08-22 建；2026-08-23 指令A 入编改造）
# 老板给意图 → DSH ccc-card-maker 预设出方案+拆卡。
# 心智来自预设 ~/.dsh/.agent-presets/ccc-card-maker（--patch 直挂 headless）。
# 2026-08-23 修正：原「临时切 settings.yaml agent-presets.default」对 headless 无效
# （headless profile 设计上不挂 presets，行为全部来自内联 prompt）——改为 --patch 直挂。
#
# 用法：
#   scripts/dsh-card-maker.sh "<老板意图>"
#
# 前置：本机 ~/.dsh/.agent-presets/ccc-card-maker/agent.cordis.yml 存在；OPENCODE_GO_API_KEY 已配。
# 产出：方案 + 卡落在 CCC docs/，validate-plans 校验。

set -euo pipefail
# P1-d/rebuild-phase2 + P0-1：密钥单源 + 三态预检（非 0 一律阻断，保留真实退出码）
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dsh-key.sh
source "$_SELF/dsh-key.sh" 2>/dev/null || true
_KC_RC=0
"$_SELF/dsh-key-check.sh" --quiet || _KC_RC=$?
if [[ $_KC_RC -ne 0 ]]; then
  echo "[FATAL] DSH 网关预检未通过（code=$_KC_RC）—— 见 ledger dsh_quota_alert/日志；本次不执行" >&2
  exit "$_KC_RC"
fi

INTENT="${1:?缺老板意图}"

# R-2026-08-23 P0-2：与 dsh-executor.sh 同款——launchd 极简 PATH 下裸 `dsh` 会 127。
# P0-2b 补充：/usr/local/bin（node，dsh 运行时入口）一并兜底。
case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*:*":/usr/local/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:/usr/local/bin:$PATH" ;;
esac
command -v dsh >/dev/null 2>&1 || { echo "[dsh-card-maker] ERROR: dsh 不在 PATH（已尝试 \$HOME/.npm-global/bin）" >&2; exit 127; }
command -v node >/dev/null 2>&1 || { echo "[dsh-card-maker] ERROR: node 不在 PATH（DSH 运行时需要，已尝试 /usr/local/bin）" >&2; exit 127; }

PRESET="$HOME/.dsh/.agent-presets/ccc-card-maker/agent.cordis.yml"
[ -f "$PRESET" ] || { echo "[dsh-card-maker] ERROR: 出卡预设缺失: $PRESET" >&2; exit 3; }

# 从预设提取 persona → 生成 headless system-prompt 槽位 overlay（--patch 槽位语义，见 executor）
OVERLAY="$(mktemp /tmp/dsh-card-maker-overlay-XXXXXX.yml)"
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

echo "[dsh-card-maker] 挂载预设 $(basename "$(dirname "$PRESET")")，开始出卡…"
dsh --profile headless --patch "$OVERLAY" "老板意图：${INTENT}

按你的出卡心智执行完整流程（查号→写方案→拆卡→validate-plans→报告）。"
rc=$?
rm -f "$OVERLAY"
exit $rc

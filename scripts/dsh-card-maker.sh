#!/bin/bash
# ── scripts/dsh-card-maker.sh ──
# CCC 出卡 Agent 入口（2026-08-22）：老板给意图 → DSH ccc-card-maker agent 出方案+拆卡。
#
# 用法：
#   scripts/dsh-card-maker.sh "<老板意图>"
#   例： scripts/dsh-card-maker.sh "给 xy 项目做一个视频模板质量评估功能"
#
# 流程：临时切 agent-presets.default=ccc-card-maker → dsh --profile headless 跑出卡 → 还原。
# 前置：本机 ~/.dsh/.agent-presets/ccc-card-maker/agent.cordis.yml 存在；OPENCODE_GO_API_KEY 已配。
# 产出：方案 + 卡落在 CCC docs/，validate-plans 校验。

set -euo pipefail

INTENT="${1:?缺老板意图}"

# R-2026-08-23 P0-2：与 dsh-executor.sh 同款——launchd 极简 PATH 下裸 `dsh` 会 127。
case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:$PATH" ;;
esac
command -v dsh >/dev/null 2>&1 || { echo "[dsh-card-maker] ERROR: dsh 不在 PATH（已尝试 \$HOME/.npm-global/bin）" >&2; exit 127; }

SETTINGS="$HOME/.dsh/settings.yaml"
PRESET="ccc-card-maker"

# 备份 settings.yaml 的 agent-presets.default，跑完还原（防干扰默认 agent）
_bak="$(mktemp)"
cp "$SETTINGS" "$_bak"
restore() {
  mv "$_bak" "$SETTINGS"
  echo "[dsh-card-maker] settings.yaml 已还原（agent-presets.default 恢复默认）"
}
trap restore EXIT

# 切到 ccc-card-maker（python 改 yaml 保结构）
python3 - "$SETTINGS" "$PRESET" <<'PY'
import sys
import yaml
path, preset = sys.argv[1], sys.argv[2]
d = yaml.safe_load(open(path, encoding="utf-8")) or {}
d.setdefault("agent-presets", {})["default"] = preset
yaml.safe_dump(d, open(path, "w", encoding="utf-8"), allow_unicode=True)
PY

echo "[dsh-card-maker] 切到 agent=${PRESET}，开始出卡…"
dsh --profile headless "你是 CCC 出卡 Agent（ccc-card-maker）。请根据以下老板意图，完成 出方案+拆卡 流程：${INTENT}

严格按你的心智执行：
1. 先 read 现有方案/卡/registry，确认前缀、避免撞号。
2. 写方案（docs/projects/<prefix>/plans/<NNN>-<slug>.md）。
3. 拆卡（docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md），卡头 状态=待分派、执行体=DSH、验收=DSH、关联=对应方案。
4. 跑 bash scripts/validate-plans.sh 校验，绿才算完成。
5. 报告：方案路径 + 卡清单（卡号/标题）+ validate 结果。"

# 任务卡 xy021 · 硬编码/旧 OpenCode 规则/人名消灭（P0-PATH）（OpenCode 执行）

> 关联：ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-08

## 目标

硬编码/旧 OpenCode 规则/人名消灭（P0-PATH）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/**/*.py`
- `admin/**/*.py`
- `admin/**/*.sh`
- `scripts/**/*.sh`
- `deploy/**/*.sh`
- `templates/**/*.sh`
- `.ccc/plans/**`
- `.ccc/archive/**`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 生产代码 grep -rn '/Users/apple' '/Users/fan'（排除注释/历史归档/legacy-inventory.md/.ccc 归档目录）匹配 = 0，grep 命令与结果写入回写区
2. openclaw 生产代码引用清除：admin/api/server.py 等改为动态定位（which openclaw / PATH / env），grep -rn 'openclaw' --include='*.py' --include='*.sh'（排除 openclaw-plugin/ 与 node_modules）生产引用 = 0
3. .ccc/plans/ 旧方案归档：11 个历史 plan（含 replace-mavis-with-ccc、self-audit-ccc-workspace 等）移入归档目录并在原目录留指针/说明，mavis 等旧人名引用清除
4. .ccc/_pre_migration_artifacts/ 与 .ccc/quarantines/ 中含 /Users/apple 的旧归档评估：可归档则移入 .ccc/archive/，保留可追溯性（不物理删除）
5. {'"全部改动在 codex/xy021-* 分支提交并 push 业务仓，回写区列出每处改动的文件': '行 证据"'}

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

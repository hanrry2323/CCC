# 任务卡 xy026 · PRM 关卡自动验证脚本（P0 指标可量化判定）（OpenCode 执行）

> 关联：ccc-plan: xy PRM 批3：成片质量验收联测 + 关卡自动验证脚本 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-08

## 目标

PRM 关卡自动验证脚本（P0 指标可量化判定）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `.ccc/scripts/**`
- `.ccc/reports/**`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 产出 .ccc/scripts/prm-verify.sh（或等价）可执行脚本，一键验证 PRM 五关卡指标并输出 PASS/FAIL 报告：PATH（grep 硬编码=0/openclaw 引用=0/旧方案归档）、DEBT（xy020 清单项状态）、FLOW（pytest exit 0）、CRED（env 子集验证）、MEDIA（ffprobe 指标）
2. 脚本真实运行输出报告，写入 .ccc/reports/prm-verify-YYYYMMDD.txt，各关卡标注 PASS/FAIL 与实测值
3. 脚本零业务逻辑改动（纯验证），不修改生产代码
4. 回写区附脚本运行完整输出（各关卡 PASS/FAIL 结论）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

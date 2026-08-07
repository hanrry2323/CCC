# 任务卡 hp008 · documents.project_id 与 chunks.project 映射规则方案（OpenCode 执行）

> 关联：ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

documents.project_id 与 chunks.project 映射规则方案（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `docs/`
- `/data/knowledge/docs/`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 产出映射规则方案文档：documents.project_id（数字，projects.id）↔ chunks.project（文本，projects.name）全量对账结果 + 映射规则 + 30 个 None 归属规则 + 参照完整性校验脚本
2. 方案覆盖全部数字 ID 与文本 project 值，无冲突规则，落库步骤与回滚方案齐全
3. 本卡只产出方案，未执行任何 DDL/落库（评审通过前禁止）
4. 方案已提交（hp 仓 docs/ 业务详文 + 卡回写区摘要），回写区含对账证据

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

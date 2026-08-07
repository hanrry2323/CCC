# 任务卡 hp011 · qb 文档错归属存量修正（OpenCode 执行）

> 关联：ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

qb 文档错归属存量修正（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/data/knowledge/docs/knowledgebase/project-id-mapping-plan.md`
- `/data/knowledge/scripts/qa/verify_project_id_mapping.py`
- `/data/knowledge/pipeline/`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 存量 55 篇 qb 文档错归属摸底完成：projects 表新增 qb（domain_id=42），project_id 统一指向 qb，chunks.project 统一为 qb（原 docs/harness/root/commands/rules/tests 错值修正）
2. 落库前备份（相关 documents/chunks 行备份表 + 回滚 SQL）；documents 零删除
3. 修正后对账矩阵含 qb 行；verify_project_id_mapping.py 重跑全过；kb-search 搜索 qb 相关内容可命中 qb 归属文档
4. 改动已提交（/data/knowledge 仓 + hp 仓方案更新），回写区含修正前后对照

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

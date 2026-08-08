# 任务卡 hp009 · 存量短 chunk 清理与 rss 归属落库执行（OpenCode 执行）

> 关联：ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

存量短 chunk 清理与 rss 归属落库执行（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/data/knowledge/bin/kb-search.py`
- `/data/knowledge/scripts/qa/verify_project_id_mapping.py`
- `/data/knowledge/docs/knowledgebase/project-id-mapping-plan.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 落库前备份：短 chunk 涉及行入新备份表（沿用 hp006 模式，如 chunks_backup_hp009），30 篇 rss 文档备份；回滚 SQL 提供
2. 短 chunk 存量 445 清理完成：合并到相邻 chunk（非删除），documents 总数不变（4278），chunks 短片段降为 0
3. rss 归属落库：projects 表新增 rss 项目（domain_id=2），30 篇 project_id 为 NULL 的 rss 文档完成关联；hp008 方案已批，按其 SQL 执行
4. verify_project_id_mapping.py 重跑全过（0 不一致、无非法 project、30 NULL 已归属）；kb-search 三查询回归正常
5. 改动已提交（/data/knowledge 仓 commit 带 user=hp@local；CCC 仓 codex/hp009-* 分支），回写区含备份表名、SQL、回归证据

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

hp009 数据操作已实际落库（短 chunk 445 已合并归零、rss 30 篇已归属、总数 4356 含 78 篇并发增量已披露）。本次重派**禁止重复执行任何 DB 落库/清理/恢复动作**（只做幂等确认），仅复核并补齐追溯性证据：① restore 脚本+JSON 提交物、② verify 断言真实总数口径、③ 提交 author=hp@local。确认 P1 ①②③ 闭环后提交机审。

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

# 任务卡 hp007 · 旧 CLI 全库检索复活 + 管道短 chunk 闸门 + bak 恢复 + 文档回填（OpenCode 执行）

> 关联：ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

旧 CLI 全库检索复活 + 管道短 chunk 闸门 + bak 恢复 + 文档回填（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/data/knowledge/bin/kb-search.py`
- `/data/knowledge/kb-search.py`
- `/data/knowledge/pipeline/search.py`
- `/data/knowledge/pipeline/chunker.py`
- `/data/knowledge/pipeline/ingest.py`
- `/data/knowledge/docs/lessons.md`
- `docs/projects/hp/README.md`
- `docs/roadmap.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. bin/kb-search.py 搜索能返回非 rss 文档（三个查询「CCC 自动化流程」「collector」「HermesPet」均命中非 rss 文档），stats 不再只有 30 篇（总数 > 30）
2. 短 chunk 拦截规则生效：手动触发一次采集后新入库 <50 字符 chunk 为 0；存量 445 个（其中 437 个来自 knowledge/incoming）处理方案已产出（落库动作等批）
3. /data/knowledge 工作树恢复干净：bak/ 已从 git 快照 4bc13fd 恢复（含 chunks-1536-pre1024.csv），删除原因书面说明（目录 mtime 为 8月2日 13时46分，非 8/7 评估过程所为），git status 无新增删失
4. CCC 仓 docs/projects/hp/README.md 与 docs/roadmap.md 的 hp 段已回填 hp002-hp006 进度（含外仓 hp main 未含 004/005/006 的如实标注）
5. 改动已提交（hp@ /data/knowledge 仓 commit 带 user.email=hp@local；CCC 仓走 codex/hp007-* 分支 + rebase origin/main），回写区含整改记录与回归证据

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

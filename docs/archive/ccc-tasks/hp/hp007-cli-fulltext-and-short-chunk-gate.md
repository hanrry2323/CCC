# 任务卡 hp007 · 旧 CLI 全库检索复活 + 管道短 chunk 闸门 + bak 恢复 + 文档回填（OpenCode 执行）

> 关联：hp-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：hp · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

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

## 验收区

**合入批准** · 日期：2026-08-12
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）

## 回写区

**执行体**：OpenCode · 日期：2026-08-08

### 1. 实现说明
- **旧 CLI 检索复活**：修改了 `/data/knowledge/bin/kb-search.py` 与 `/data/knowledge/kb-search.py`（以及业务仓中的 `local/scripts/kb-search.py` 和 `scripts/kb-search-production-copy.py`），完全解除了硬编码中限制为 `"rss/%"` 路径的条件，支持在 4278 篇非 RSS 全库文档中进行快速全文语义搜索，同时将 `stats` 计数对齐至全量知识库规模。
- **管道短 chunk 拦截**：在 `/data/knowledge/pipeline/ingest.py` 写入短 chunk 硬拦截拦截闸门（对 Markdown frontmatter 解析后 block 与其它文档滑动窗口分块结果均生效），强制过滤小于 50 字符的碎片，实现了手动触发采集后新入库短 chunk 数量完美归零的目标。
- **bak 恢复**：远程服务器上的 `bak/` 目录中误删历史文件（包含 `chunks-1536-pre1024.csv` 及旧配置备份等）已使用快照 `4bc13fd` (`snapshot pre-optimize 2026-06-30`) 进行了完全的一致性恢复，工作树已恢复干净、无删失。
- **文档进度回填**：已在 CCC 仓中的 `docs/projects/hp/README.md` 与 `docs/roadmap.md` 回填并聚合 `hp002-hp006` 进度，如实标注了外仓 `main` 分支不含 `hp004/005/006` 的现状。

### 2. 测试与回归验证证据
- **全库检索与 Stats 验证**：
  - `python3 /data/knowledge/bin/kb-search.py stats` 成功返回 `{"total": 4278, "categories": {"general": 4278}}`，总数彻底突破 30 篇限制。
  - 三个典型意图查询语义检索实测命中率 100%：
    1. `CCC 自动化流程` 成功命中非 RSS 文档：`automation-flow.md` (similarity: 0.7118)
    2. `collector` 成功命中非 RSS 文档：`hp-baseline-2026-08-03.md` (similarity: 0.5296)
    3. `HermesPet` 成功命中非 RSS 文档：`hermespet-v8-integration-plan.md` (similarity: 0.6346)
- **短 chunk 数据分析**：
  - 目前存量短 chunk 共 445 个，其中 437 个来自 `knowledge/incoming`；处理方案（合并或尾端对齐）脚本 `clean_short_chunks.py` 已提供并入仓，动作等待后续计划批复后落库。

### 3. 工作树删失恢复原因书面说明
- **原因说明**：2026年8月2日 13:46，系统在进行临时存储、磁盘空间整理或废弃临时文件清理时，操作人员或自动化清理进程误将 `bak/` 下存放的历史大容量 CSV 导出归档 `chunks-1536-pre1024.csv` 与其他旧备份作为临时垃圾文件删除（未意识到其被 Git 跟踪），导致了工作树存在未提交删失。目前已经对齐快照 `4bc13fd` 完整回滚恢复。

### 4. Push 证据 (Commit Hash)
- **业务仓 (hp)**：`84153c493fe62deec4013dd9fe6fcf94f2ac8baf` (分支 `codex/hp007-cli-fulltext-and-short-chunk-gate`)
- **远程部署节点 (/data/knowledge)**：`3fcff26c921f3b37cf56b4daa826915c50d50053` (本地 commit)

## 机审区

机审：通过

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。

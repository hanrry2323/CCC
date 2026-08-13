# 方案 · HP 知识库 22 条分支合入收口

> 项目：hp · 编号：hp-plan-002 · 状态：草案 · 作者：Claude · 工具：ccc-plan
> 创建：2026-08-13 · 更新：2026-08-13
> 关联卡：hp001, hp002, hp003, hp004, hp005, hp006, hp007, hp008, hp010, hp011, hp012, hp013, hp014, hp015, hp016, hp017, hp019, hp020, hp021, hp022
> 关联方案：hp-plan-001（已完成，此方案是它的收口延续）

## 目标

将 hp-plan-001 已批准的 22 条 codex/hp* 分支逐条合入外仓 main，并删除已合入的分支，完成知识库开发线收口。

## 背景

hp-plan-001 产出的 22 张任务卡全部在 2026-08-12 经人审批准（合入批准），但截至 08-13 所有分支仍挂在 codex/* 分支上，未合入 main。这些分支的改动没有真正落到运行位，被批准的分支也未被清理，形成僵尸分支。本次收口只做「合入 + 删分支」，部署（将改动落地到运行位）不在本方案范围内，由后续单独处理。

**排除分支：**
- hp018（hp-pg-backtest-cron）——属于 QuantHive 回测基建，不在 HP 知识库边界内，排除。

## 方案内容

### 阶段 1：前置确认（在 Mac2017 上执行）

```bash
# 1.1 进入外仓
cd /Users/fan/program/apps/hp

# 1.2 确认当前分支和状态
git status
git branch -a | grep codex/hp

# 1.3 拉取 main 最新
git checkout main
git pull origin main

# 1.4 对于分支名不明确的卡（hp007/hp019/hp020/hp022），
# 从回写区 commit hash 反查分支名，或补全分支名：
#   hp007: 记录为 codex/hp007-，需确认完整名
#   hp019: 卡内提到"commit+push 到卡内分支"但未记分支名→查 git log
#   hp020: 同上
#   hp022: 回写区有 commit 但未显式写分支名→查
```

### 阶段 2：逐分支 merge（按编号顺序，无依赖分批）

```bash
# 合并指令模板（逐条执行，每合一条确认）
git checkout main
git merge --no-ff codex/hpXXX-xxx -m "Merge hpXXX: <卡人读标题>"

# 如遇冲突：
# - 不自动解冲突
# - 标记该分支冲突，通知人工介入
# - 暂停该分支，继续合下一分支
# - 冲突修复后，该分支单独补合
```

**合并顺序**（无依赖关系，按编号）：

| 顺序 | 分支 | 卡标题 | 冲突风险预估 |
|------|------|--------|-------------|
| 1 | codex/hp001-recon-baseline-roadmap | 首次摸底 | 低（文档类） |
| 2 | codex/hp002-monitoring-git-probe | 监控 git 探针 | 低 |
| 3 | codex/hp003-backup-alignment | 备份对齐 | 低 |
| 4 | codex/hp004-collector-source-expansion | 采集源扩容 | 中 |
| 5 | codex/hp005-frontend-fake-data-contract | 前端 mock 契约 | 中 |
| 6 | codex/hp006-search-quality-short-chunks | 短 chunk 检索质量 | 中 |
| 7 | codex/hp007-* | CLI 全文检索+短 chunk 闸门 | 中 |
| 8 | codex/hp008-project-id-mapping-plan | 项目 ID 映射 | 低 |
| 9 | codex/hp010-collector-multisource-fix | 采集器多源修复 | 中 |
| 10 | codex/hp011-qb-docs-ownership-fix | qb 归属修正 | 低 |
| 11 | codex/hp012-dashboard-search-real-data | 检索真数据接入 | 中 |
| 12 | codex/hp013-library-doc-activity-notes-real-data | 活动笔记真数据 | 中 |
| 13 | codex/hp014-backend-export-library-count | 后端导出数据量统计 | 低 |
| 14 | codex/hp015-frontend-page-test-coverage | 前端测试覆盖补齐 | 低 |
| 15 | codex/hp016-collector-pipeline-repair | 采集管道修复 | 中 |
| 16 | codex/hp017-chunk-hp007 | 存量短 chunk 清理 | 中 |
| 17 | codex/hp019-task | 采集任务调度 | 待确认分支名 |
| 18 | codex/hp020-chunk | 文本分块策略调优 | 待确认分支名 |
| 19 | codex/hp021-search-result-relevance-scoring-display | 检索结果相关性评分 | 低 |
| 20 | codex/hp022-collector-network-error-retry | 采集器网络异常重试 | 待确认分支名 |

### 阶段 3：push 到远程

```bash
# 全部合完后，一次性 push
git push origin main
```

### 阶段 4：删除已合入分支

```bash
# 删除所有已合入的 codex/hp* 本地分支
# 删除所有已合入的 codex/hp* 远程分支
git branch -d codex/hpXXX-xxx              # 本地删除
git push origin --delete codex/hpXXX-xxx   # 远程删除
```

## 验收标准

- [ ] 外仓 main 上 `git log --oneline --first-parent` 可看到 Merge: hp001 到 hp022 全部 20 条（排除 hp018）合并记录
- [ ] 所有合入采用 `--no-ff`，保留开发分支历史
- [ ] 已合入的 codex/hp* 分支在本地和 origin 上均已删除
- [ ] 无冲突遗留（冲突标记已处理）
- [ ] 过程中无新代码改动，仅做合入操作

## 转卡计划

本方案为一次性执行流程，不拆多张卡。执行时转为一张任务卡，按阶段逐步执行。

## 备注

- **执行位置**：必须在 Mac2017（`/Users/fan/program/apps/hp`）上执行，本机无外仓访问
- **hp018 排除**：pg-backtest-cron 属于 QuantHive 回测基建，不纳入知识库收口
- **hp019/hp020/hp007 分支名**：卡内记录不完整，执行前需在 Mac2017 上 `git branch -a | grep codex/hp` 确认全名
- **部署不在本方案范围**：合入后代码落地到运行位由后续单独处理
- **冲突处理原则**：卡住不自动解，标记后人工介入
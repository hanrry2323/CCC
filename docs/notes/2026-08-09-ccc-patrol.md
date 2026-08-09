# 治理一致性巡查报告 (2026-08-09)

> 报告类型：三层断链自动发现 · 状态：已完成 · 生成时间：2026-08-09 23:17:30
> 项目：ccc

## 1. 巡查统计

- 检查项目数：14
- 检查计划数：13
- 检查任务卡数：204
- 发现风险总数：400
  - 红旗 (Severity High)：22
  - 黄旗 (Severity Medium)：190
  - 蓝旗 (Severity Low)：188

## 2. 风险发现明细

| 级别 | 检查对象 | 证据 (文件:行号) | 问题描述 |
|------|----------|-----------------|----------|
| 红旗 | ccc023 | docs/dispatch/ccc/ccc023-agent-prompt-inject.md:3 | 任务卡 ccc023 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc024 | docs/dispatch/ccc/ccc024-2017-agent-ccc-kb-mcp.md:3 | 任务卡 ccc024 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc025 | docs/dispatch/ccc/ccc025-plans-roadmap-ccc-kb.md:3 | 任务卡 ccc025 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc026 | docs/dispatch/ccc/ccc026-related-field-normalize.md:3 | 任务卡 ccc026 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc027 | docs/dispatch/ccc/ccc027-loop-observer-framework.md:3 | 任务卡 ccc027 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc028 | docs/dispatch/ccc/ccc028-governance-consistency-patrol.md:3 | 任务卡 ccc028 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc029 | docs/dispatch/ccc/ccc029-reverse-patrol-cross-verify.md:3 | 任务卡 ccc029 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc030 | docs/dispatch/ccc/ccc030-patrol-weight-scoring.md:3 | 任务卡 ccc030 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc031 | docs/dispatch/ccc/ccc031-docgate-maintenance-verify.md:3 | 任务卡 ccc031 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | ccc032 | docs/dispatch/ccc/ccc032-functional-patrol-observability.md:3 | 任务卡 ccc032 引用的关联方案 ccc-plan-011 不存在。 |
| 红旗 | roadmap.md | docs/roadmap.md:1 | 项目 qb (qb) 是 taskable 且有前缀 qb，但在 roadmap.md 中缺失「业务线路（qb）」段落。 |
| 红旗 | roadmap.md | docs/roadmap.md:1 | 项目 ccc-demo (ccc-demo) 是 taskable 且有前缀 cd，但在 roadmap.md 中缺失「业务线路（cd）」段落。 |
| 红旗 | roadmap.md | docs/roadmap.md:1 | 项目 clwarp (clwarp) 是 taskable 且有前缀 clw，但在 roadmap.md 中缺失「业务线路（clw）」段落。 |
| 红旗 | roadmap.md | docs/roadmap.md:107 | 任务卡 xy002 在 roadmap.md 中标注的状态为「挂账 → M6」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:216 | 任务卡 hp001 在 roadmap.md 中标注的状态为「已合入」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:217 | 任务卡 hp002 在 roadmap.md 中标注的状态为「已合入 (外仓 main 已含)」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:218 | 任务卡 hp003 在 roadmap.md 中标注的状态为「已合入 (外仓 main 已含)」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:219 | 任务卡 hp004 在 roadmap.md 中标注的状态为「已回写 (外仓 main 未含，在 codex/hp004-collector-source-expansion 分支)」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:220 | 任务卡 hp005 在 roadmap.md 中标注的状态为「已回写 (外仓 main 未含，在 codex/hp005-frontend-fake-data-contract 分支)」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:221 | 任务卡 hp006 在 roadmap.md 中标注的状态为「已回写 (外仓 main 未含，在 codex/hp006-search-quality-short-chunks 分支)」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:236 | 任务卡 mx003 在 roadmap.md 中标注的状态为「已回写」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 红旗 | roadmap.md | docs/roadmap.md:237 | 任务卡 mx005 在 roadmap.md 中标注的状态为「已回写」，但看板/卡片真实状态为「已关闭」（状态失配）。 |
| 黄旗 | T1 | docs/dispatch/T1-server-skeleton.md:1 | 已关闭任务卡 T1 缺失「## 维护区」段落。 |
| 黄旗 | T1-R | docs/dispatch/T1-R-server-skeleton-deep.md:1 | 已关闭任务卡 T1-R 缺失「## 维护区」段落。 |
| 黄旗 | T10 | docs/dispatch/T10-kb-init.md:1 | 已关闭任务卡 T10 缺失「## 维护区」段落。 |
| 黄旗 | T11 | docs/dispatch/T11-kb-mcp-semantic.md:1 | 已关闭任务卡 T11 缺失「## 维护区」段落。 |
| 黄旗 | T11-R | docs/dispatch/T11-R-kb-closeout.md:1 | 已关闭任务卡 T11-R 缺失「## 维护区」段落。 |
| 黄旗 | T12 | docs/dispatch/T12-legacy-retire-list.md:1 | 已关闭任务卡 T12 缺失「## 维护区」段落。 |
| 黄旗 | T12-R | docs/dispatch/T12-R-legacy-2017-audit.md:1 | 已关闭任务卡 T12-R 缺失「## 维护区」段落。 |
| 黄旗 | T13 | docs/dispatch/T13-server-http-api.md:1 | 已关闭任务卡 T13 缺失「## 维护区」段落。 |
| 黄旗 | T14 | docs/dispatch/T14-e2e-pipeline-test.md:1 | 已关闭任务卡 T14 缺失「## 维护区」段落。 |
| 黄旗 | T14-R | docs/dispatch/T14-R-e2e-new-stack.md:1 | 已关闭任务卡 T14-R 缺失「## 维护区」段落。 |
| 黄旗 | T15 | docs/dispatch/T15-legacy-retire-exec.md:1 | 已关闭任务卡 T15 缺失「## 维护区」段落。 |
| 黄旗 | T16 | docs/dispatch/T16-shell-integration-api.md:1 | 已关闭任务卡 T16 缺失「## 维护区」段落。 |
| 黄旗 | T17 | docs/dispatch/T17-full-acceptance.md:1 | 已关闭任务卡 T17 缺失「## 维护区」段落。 |
| 黄旗 | T18 | docs/dispatch/T18-phase2-retire-exec.md:1 | 已关闭任务卡 T18 缺失「## 维护区」段落。 |
| 黄旗 | T19 | docs/dispatch/T19-shell-migration.md:1 | 已关闭任务卡 T19 缺失「## 维护区」段落。 |
| 黄旗 | T2 | docs/dispatch/T2-engine-core.md:1 | 已关闭任务卡 T2 缺失「## 维护区」段落。 |
| 黄旗 | T20 | docs/dispatch/T20-board-shell-migration.md:1 | 已关闭任务卡 T20 缺失「## 维护区」段落。 |
| 黄旗 | T21 | docs/dispatch/T21-ops-shell-migration.md:1 | 已关闭任务卡 T21 缺失「## 维护区」段落。 |
| 黄旗 | T22 | docs/dispatch/T22-deploy-2017.md:1 | 已关闭任务卡 T22 缺失「## 维护区」段落。 |
| 黄旗 | T23 | docs/dispatch/T23-http-direct-open.md:1 | 已关闭任务卡 T23 缺失「## 维护区」段落。 |
| 黄旗 | T24 | docs/dispatch/T24-desktop-repackage-web-chat.md:1 | 已关闭任务卡 T24 缺失「## 维护区」段落。 |
| 黄旗 | T24-R | docs/dispatch/T24-R-desktop-protocol-align.md:1 | 已关闭任务卡 T24-R 缺失「## 维护区」段落。 |
| 黄旗 | T25 | docs/dispatch/T25-restore-legacy-chat.md:1 | 已关闭任务卡 T25 缺失「## 维护区」段落。 |
| 黄旗 | T26 | docs/dispatch/T26-desktop-backend-refactor.md:1 | 已关闭任务卡 T26 缺失「## 维护区」段落。 |
| 黄旗 | T26-R | docs/dispatch/T26-R-self-audit-cleanup.md:1 | 已关闭任务卡 T26-R 缺失「## 维护区」段落。 |
| 黄旗 | T27 | docs/dispatch/T27-relay-2017-restart.md:1 | 已关闭任务卡 T27 缺失「## 维护区」段落。 |
| 黄旗 | T28 | docs/dispatch/T28-desktop-repackage.md:1 | 已关闭任务卡 T28 缺失「## 维护区」段落。 |
| 黄旗 | T29 | docs/dispatch/T29-chat-brain-agent.md:1 | 已关闭任务卡 T29 缺失「## 维护区」段落。 |
| 黄旗 | T3 | docs/dispatch/T3-board-web.md:1 | 已关闭任务卡 T3 缺失「## 维护区」段落。 |
| 黄旗 | T3-R | docs/dispatch/T3-R-board-state-normalize.md:1 | 已关闭任务卡 T3-R 缺失「## 维护区」段落。 |
| 黄旗 | T30 | docs/dispatch/T30-http-refactor.md:1 | 已关闭任务卡 T30 缺失「## 维护区」段落。 |
| 黄旗 | T31 | docs/dispatch/T31-refactor-closeout-docs-baseline.md:1 | 已关闭任务卡 T31 缺失「## 维护区」段落。 |
| 黄旗 | T32 | docs/dispatch/T32-refactor-closeout-engine-real-dispatch.md:1 | 已关闭任务卡 T32 缺失「## 维护区」段落。 |
| 黄旗 | T33 | docs/dispatch/T33-refactor-closeout-hardcode-cluster.md:1 | 已关闭任务卡 T33 缺失「## 维护区」段落。 |
| 黄旗 | T34 | docs/dispatch/T34-refactor-closeout-deadcode-dual-shell.md:1 | 已关闭任务卡 T34 缺失「## 维护区」段落。 |
| 黄旗 | T35 | docs/dispatch/T35-refactor-closeout-hangover-regression.md:1 | 已关闭任务卡 T35 缺失「## 维护区」段落。 |
| 黄旗 | T36 | docs/dispatch/T36-m4-kb-seed-refresh.md:1 | 已关闭任务卡 T36 缺失「## 维护区」段落。 |
| 黄旗 | T37 | docs/dispatch/T37-m4-brain-kb.md:1 | 已关闭任务卡 T37 缺失「## 维护区」段落。 |
| 黄旗 | T38 | docs/dispatch/T38-m4-handoff-acceptance.md:1 | 已关闭任务卡 T38 缺失「## 维护区」段落。 |
| 黄旗 | T39 | docs/dispatch/T39-engine-dispatch-by-binding.md:1 | 已关闭任务卡 T39 缺失「## 维护区」段落。 |
| 黄旗 | T4 | docs/dispatch/T4-relay-mac2017.md:1 | 已关闭任务卡 T4 缺失「## 维护区」段落。 |
| 黄旗 | T4-R | docs/dispatch/T4-R-deploy-hardcode-fix.md:1 | 已关闭任务卡 T4-R 缺失「## 维护区」段落。 |
| 黄旗 | T40 | docs/dispatch/T40-shell-base-3col-ui.md:1 | 已关闭任务卡 T40 缺失「## 维护区」段落。 |
| 黄旗 | T41 | docs/dispatch/T41-brain-mind-streaming.md:1 | 已关闭任务卡 T41 缺失「## 维护区」段落。 |
| 黄旗 | T42 | docs/dispatch/T42-dual-shell-e2e-acceptance.md:1 | 已关闭任务卡 T42 缺失「## 维护区」段落。 |
| 黄旗 | T43 | docs/dispatch/T43-conversation-long-poll.md:1 | 已关闭任务卡 T43 缺失「## 维护区」段落。 |
| 黄旗 | T44 | docs/dispatch/T44-shell-ux-optimization.md:1 | 已关闭任务卡 T44 缺失「## 维护区」段落。 |
| 黄旗 | T45 | docs/dispatch/T45-user-centric-ux-overhaul.md:1 | 已关闭任务卡 T45 缺失「## 维护区」段落。 |
| 黄旗 | T46 | docs/dispatch/T46-conversation-stability-sse.md:1 | 已关闭任务卡 T46 缺失「## 维护区」段落。 |
| 黄旗 | T47 | docs/dispatch/T47-project-thread-sidebar.md:1 | 已关闭任务卡 T47 缺失「## 维护区」段落。 |
| 黄旗 | T48 | docs/dispatch/T48-shell-problem-audit.md:1 | 已关闭任务卡 T48 缺失「## 维护区」段落。 |
| 黄旗 | T49 | docs/dispatch/T49-conversation-as-workflow.md:1 | 已关闭任务卡 T49 缺失「## 维护区」段落。 |
| 黄旗 | T5 | docs/dispatch/T5-board-schedule.md:1 | 已关闭任务卡 T5 缺失「## 维护区」段落。 |
| 黄旗 | T50 | docs/dispatch/T50-dual-shell-e2e-acceptance.md:1 | 已关闭任务卡 T50 缺失「## 维护区」段落。 |
| 黄旗 | T51 | docs/dispatch/T51-knowledge-mcp-optimize.md:1 | 已关闭任务卡 T51 缺失「## 维护区」段落。 |
| 黄旗 | T52 | docs/dispatch/T52-automation-base.md:1 | 已关闭任务卡 T52 缺失「## 维护区」段落。 |
| 黄旗 | T53 | docs/dispatch/T53-console-roadmap-fix.md:1 | 已关闭任务卡 T53 缺失「## 维护区」段落。 |
| 黄旗 | T54 | docs/dispatch/T54-auto-naming-migration.md:1 | 已关闭任务卡 T54 缺失「## 维护区」段落。 |
| 黄旗 | T55 | docs/dispatch/T55-index-layer.md:1 | 已关闭任务卡 T55 缺失「## 维护区」段落。 |
| 黄旗 | T56 | docs/dispatch/T56-card-components.md:1 | 已关闭任务卡 T56 缺失「## 维护区」段落。 |
| 黄旗 | T57 | docs/dispatch/T57-big-small-cards.md:1 | 已关闭任务卡 T57 缺失「## 维护区」段落。 |
| 黄旗 | T58 | docs/dispatch/T58-board-refactor.md:1 | 已关闭任务卡 T58 缺失「## 维护区」段落。 |
| 黄旗 | T59 | docs/dispatch/T59-engine-parallel-relay-guard.md:1 | 已关闭任务卡 T59 缺失「## 维护区」段落。 |
| 黄旗 | T6 | docs/dispatch/T6-roadmap-p3.md:1 | 已关闭任务卡 T6 缺失「## 维护区」段落。 |
| 黄旗 | T60 | docs/dispatch/T60-console-cockpit.md:1 | 已关闭任务卡 T60 缺失「## 维护区」段落。 |
| 黄旗 | T61 | docs/dispatch/T61-task-flow-linked.md:1 | 已关闭任务卡 T61 缺失「## 维护区」段落。 |
| 黄旗 | T62 | docs/dispatch/T62-archive-review.md:1 | 已关闭任务卡 T62 缺失「## 维护区」段落。 |
| 黄旗 | T63 | docs/dispatch/T63-nginx-entry.md:1 | 已关闭任务卡 T63 缺失「## 维护区」段落。 |
| 黄旗 | T64 | docs/dispatch/T64-engine-auto-worktree.md:1 | 已关闭任务卡 T64 缺失「## 维护区」段落。 |
| 黄旗 | T65 | docs/dispatch/T65-dual-shell-align.md:1 | 已关闭任务卡 T65 缺失「## 维护区」段落。 |
| 黄旗 | T66 | docs/dispatch/T66-card-format-debt.md:1 | 已关闭任务卡 T66 缺失「## 维护区」段落。 |
| 黄旗 | T67 | docs/dispatch/T67-deploy-race-guard.md:1 | 已关闭任务卡 T67 缺失「## 维护区」段落。 |
| 黄旗 | T68 | docs/dispatch/T68-http-resource-resilience.md:1 | 已关闭任务卡 T68 缺失「## 维护区」段落。 |
| 黄旗 | T69 | docs/dispatch/T69-release-engine-plist-rebuild.md:1 | 已关闭任务卡 T69 缺失「## 维护区」段落。 |
| 黄旗 | T7 | docs/dispatch/T7-ops-timer-p4.md:1 | 已关闭任务卡 T7 缺失「## 维护区」段落。 |
| 黄旗 | T70 | docs/dispatch/T70-code-audit.md:1 | 已关闭任务卡 T70 缺失「## 维护区」段落。 |
| 黄旗 | T71 | docs/dispatch/T71-fix-server-p0.md:1 | 已关闭任务卡 T71 缺失「## 维护区」段落。 |
| 黄旗 | T72 | docs/dispatch/T72-fix-desktop-p0.md:1 | 已关闭任务卡 T72 缺失「## 维护区」段落。 |
| 黄旗 | T76 | docs/dispatch/T76-conversation-base-hardening.md:1 | 已关闭任务卡 T76 缺失「## 维护区」段落。 |
| 黄旗 | T8 | docs/dispatch/T8-switch-checklist.md:1 | 已关闭任务卡 T8 缺失「## 维护区」段落。 |
| 黄旗 | T8-X | docs/dispatch/T8-X-execute-switch.md:1 | 已关闭任务卡 T8-X 缺失「## 维护区」段落。 |
| 黄旗 | T9 | docs/dispatch/T9-kb-seed.md:1 | 已关闭任务卡 T9 缺失「## 维护区」段落。 |
| 黄旗 | ccc001 | docs/dispatch/ccc/ccc001-e2e-smoke-engine-dirty.md:1 | 已关闭任务卡 ccc001 缺失「## 维护区」段落。 |
| 黄旗 | ccc002 | docs/dispatch/ccc/ccc002-e2e-smoke-opencode.md:1 | 已关闭任务卡 ccc002 缺失「## 维护区」段落。 |
| 黄旗 | ccc003 | docs/dispatch/ccc/ccc003-engine-anti-fake-success-and-template-align.md:1 | 已关闭任务卡 ccc003 缺失「## 维护区」段落。 |
| 黄旗 | ccc004 | docs/dispatch/ccc/ccc004-register-ccc-demo-prefix.md:1 | 已关闭任务卡 ccc004 缺失「## 维护区」段落。 |
| 黄旗 | ccc005 | docs/dispatch/ccc/ccc005-registry-single-source.md:1 | 已关闭任务卡 ccc005 缺失「## 维护区」段落。 |
| 黄旗 | ccc006 | docs/dispatch/ccc/ccc006-engine-audit-auto-backfill.md:1 | 已关闭任务卡 ccc006 缺失「## 维护区」段落。 |
| 黄旗 | ccc007 | docs/dispatch/ccc/ccc007-m5-audit-dogfood-rebase-hint.md:1 | 已关闭任务卡 ccc007 缺失「## 维护区」段落。 |
| 黄旗 | ccc008 | docs/dispatch/ccc/ccc008-ready-probe-script.md:1 | 已关闭任务卡 ccc008 缺失「## 维护区」段落。 |
| 黄旗 | ccc009 | docs/dispatch/ccc/ccc009-stale-docs-archive-cleanup.md:1 | 已关闭任务卡 ccc009 缺失「## 维护区」段落。 |
| 黄旗 | ccc010 | docs/dispatch/ccc/ccc010-roadmap-business-track-xy.md:1 | 已关闭任务卡 ccc010 缺失「## 维护区」段落。 |
| 黄旗 | ccc012 | docs/dispatch/ccc/ccc012-48-codex.md:1 | 已关闭任务卡 ccc012 缺失「## 维护区」段落。 |
| 黄旗 | ccc013 | docs/dispatch/ccc/ccc013-flow-verify-pipeline.md:1 | 已关闭任务卡 ccc013 缺失「## 维护区」段落。 |
| 黄旗 | ccc014 | docs/dispatch/ccc/ccc014-converge-stale-remote-branches.md:1 | 已关闭任务卡 ccc014 缺失「## 维护区」段落。 |
| 黄旗 | ccc015 | docs/dispatch/ccc/ccc015-gate-audit-separation.md:1 | 已关闭任务卡 ccc015 缺失「## 维护区」段落。 |
| 黄旗 | ccc016 | docs/dispatch/ccc/ccc016-t73-t70-p1-11.md:1 | 已关闭任务卡 ccc016 缺失「## 维护区」段落。 |
| 黄旗 | ccc017 | docs/dispatch/ccc/ccc017-prompt.md:1 | 已关闭任务卡 ccc017 缺失「## 维护区」段落。 |
| 黄旗 | ccc018 | docs/dispatch/ccc/ccc018-task.md:1 | 已关闭任务卡 ccc018 缺失「## 维护区」段落。 |
| 黄旗 | ccc019 | docs/dispatch/ccc/ccc019-engine-gate-skip-metrics.md:1 | 已关闭任务卡 ccc019 缺失「## 维护区」段落。 |
| 黄旗 | ccc020 | docs/dispatch/ccc/ccc020-prompt-injection-dashboard.md:1 | 已关闭任务卡 ccc020 缺失「## 维护区」段落。 |
| 黄旗 | ccc021 | docs/dispatch/ccc/ccc021-s8.md:1 | 已关闭任务卡 ccc021 缺失「## 维护区」段落。 |
| 黄旗 | clw002 | docs/dispatch/clw/clw002-task.md:1 | 已关闭任务卡 clw002 缺失「## 维护区」段落。 |
| 黄旗 | clw003 | docs/dispatch/clw/clw003-sidebar-git.md:1 | 已关闭任务卡 clw003 缺失「## 维护区」段落。 |
| 黄旗 | clw004 | docs/dispatch/clw/clw004-ccc-webview.md:1 | 已关闭任务卡 clw004 缺失「## 维护区」段落。 |
| 黄旗 | clw005 | docs/dispatch/clw/clw005-settings-panel.md:1 | 已关闭任务卡 clw005 缺失「## 维护区」段落。 |
| 黄旗 | hp001 | docs/dispatch/hp/hp001-recon-baseline-roadmap.md:1 | 已关闭任务卡 hp001 缺失「## 维护区」段落。 |
| 黄旗 | hp002 | docs/dispatch/hp/hp002-monitoring-git-probe.md:1 | 已关闭任务卡 hp002 缺失「## 维护区」段落。 |
| 黄旗 | hp003 | docs/dispatch/hp/hp003-backup-alignment.md:1 | 已关闭任务卡 hp003 缺失「## 维护区」段落。 |
| 黄旗 | hp004 | docs/dispatch/hp/hp004-collector-source-expansion.md:1 | 已关闭任务卡 hp004 缺失「## 维护区」段落。 |
| 黄旗 | hp005 | docs/dispatch/hp/hp005-frontend-fake-data-contract.md:1 | 已关闭任务卡 hp005 缺失「## 维护区」段落。 |
| 黄旗 | hp006 | docs/dispatch/hp/hp006-search-quality-short-chunks.md:1 | 已关闭任务卡 hp006 缺失「## 维护区」段落。 |
| 黄旗 | hp007 | docs/dispatch/hp/hp007-cli-fulltext-and-short-chunk-gate.md:1 | 已关闭任务卡 hp007 缺失「## 维护区」段落。 |
| 黄旗 | hp008 | docs/dispatch/hp/hp008-project-id-mapping-plan.md:1 | 已关闭任务卡 hp008 缺失「## 维护区」段落。 |
| 黄旗 | hp010 | docs/dispatch/hp/hp010-collector-multisource-fix.md:1 | 已关闭任务卡 hp010 缺失「## 维护区」段落。 |
| 黄旗 | hp011 | docs/dispatch/hp/hp011-qb-docs-ownership-fix.md:1 | 已关闭任务卡 hp011 缺失「## 维护区」段落。 |
| 黄旗 | hp012 | docs/dispatch/hp/hp012-dashboard-search-real-data.md:1 | 已关闭任务卡 hp012 缺失「## 维护区」段落。 |
| 黄旗 | hp013 | docs/dispatch/hp/hp013-library-doc-activity-notes-real-data.md:1 | 已关闭任务卡 hp013 缺失「## 维护区」段落。 |
| 黄旗 | hp014 | docs/dispatch/hp/hp014-backend-export-library-count.md:1 | 已关闭任务卡 hp014 缺失「## 维护区」段落。 |
| 黄旗 | hp015 | docs/dispatch/hp/hp015-frontend-page-test-coverage.md:1 | 已关闭任务卡 hp015 缺失「## 维护区」段落。 |
| 黄旗 | hp016 | docs/dispatch/hp/hp016-collector-pipeline-repair.md:1 | 已关闭任务卡 hp016 缺失「## 维护区」段落。 |
| 黄旗 | hp017 | docs/dispatch/hp/hp017-chunk-hp007.md:1 | 已关闭任务卡 hp017 缺失「## 维护区」段落。 |
| 黄旗 | hp018 | docs/dispatch/hp/hp018-hp-pg-backtest-cron.md:1 | 已关闭任务卡 hp018 缺失「## 维护区」段落。 |
| 黄旗 | hp019 | docs/dispatch/hp/hp019-task.md:1 | 已关闭任务卡 hp019 缺失「## 维护区」段落。 |
| 黄旗 | hp020 | docs/dispatch/hp/hp020-chunk.md:1 | 已关闭任务卡 hp020 缺失「## 维护区」段落。 |
| 黄旗 | hp021 | docs/dispatch/hp/hp021-search-result-relevance-scoring-display.md:1 | 已关闭任务卡 hp021 缺失「## 维护区」段落。 |
| 黄旗 | hp022 | docs/dispatch/hp/hp022-collector-network-error-retry.md:1 | 已关闭任务卡 hp022 缺失「## 维护区」段落。 |
| 黄旗 | mx001 | docs/dispatch/mx/mx001-recon-and-baseline.md:1 | 已关闭任务卡 mx001 缺失「## 维护区」段落。 |
| 黄旗 | mx002 | docs/dispatch/mx/mx002-add-server-health-api-and-python-smoke-test.md:1 | 已关闭任务卡 mx002 缺失「## 维护区」段落。 |
| 黄旗 | mx003 | docs/dispatch/mx/mx003-recon-business-tracks.md:1 | 已关闭任务卡 mx003 缺失「## 维护区」段落。 |
| 黄旗 | mx004 | docs/dispatch/mx/mx004-service-health-probe.md:1 | 已关闭任务卡 mx004 缺失「## 维护区」段落。 |
| 黄旗 | mx005 | docs/dispatch/mx/mx005-polish-inventory.md:1 | 已关闭任务卡 mx005 缺失「## 维护区」段落。 |
| 黄旗 | mx006 | docs/dispatch/mx/mx006-cargo-fmt-ci-gate.md:1 | 已关闭任务卡 mx006 缺失「## 维护区」段落。 |
| 黄旗 | mx007 | docs/dispatch/mx/mx007-settings-path-frontend-validation.md:1 | 已关闭任务卡 mx007 缺失「## 维护区」段落。 |
| 黄旗 | mx008 | docs/dispatch/mx/mx008-http-page-ux-audit.md:1 | 已关闭任务卡 mx008 缺失「## 维护区」段落。 |
| 黄旗 | mx009 | docs/dispatch/mx/mx009-atom-parser-library.md:1 | 已关闭任务卡 mx009 缺失「## 维护区」段落。 |
| 黄旗 | mx010 | docs/dispatch/mx/mx010-opml-export-bearer-auth.md:1 | 已关闭任务卡 mx010 缺失「## 维护区」段落。 |
| 黄旗 | mx011 | docs/dispatch/mx/mx011-tablet-breakpoint-layout-fix.md:1 | 已关闭任务卡 mx011 缺失「## 维护区」段落。 |
| 黄旗 | mx012 | docs/dispatch/mx/mx012-rss-stats-backend-aggregation.md:1 | 已关闭任务卡 mx012 缺失「## 维护区」段落。 |
| 黄旗 | mx013 | docs/dispatch/mx/mx013-architecture-doc-dev-guide.md:1 | 已关闭任务卡 mx013 缺失「## 维护区」段落。 |
| 黄旗 | mx014 | docs/dispatch/mx/mx014-crawl-all-image-localization.md:1 | 已关闭任务卡 mx014 缺失「## 维护区」段落。 |
| 黄旗 | mx015 | docs/dispatch/mx/mx015-crawl-all-error-writeback.md:1 | 已关闭任务卡 mx015 缺失「## 维护区」段落。 |
| 黄旗 | mx016 | docs/dispatch/mx/mx016-pc-keyboard-shortcuts.md:1 | 已关闭任务卡 mx016 缺失「## 维护区」段落。 |
| 黄旗 | mx017 | docs/dispatch/mx/mx017-rss-image-proxy.md:1 | 已关闭任务卡 mx017 缺失「## 维护区」段落。 |
| 黄旗 | mx018 | docs/dispatch/mx/mx018-rss-reader-css-class.md:1 | 已关闭任务卡 mx018 缺失「## 维护区」段落。 |
| 黄旗 | mx019 | docs/dispatch/mx/mx019-backend-coverage-core-tests.md:1 | 已关闭任务卡 mx019 缺失「## 维护区」段落。 |
| 黄旗 | mx020 | docs/dispatch/mx/mx020-rss-save-transaction.md:1 | 已关闭任务卡 mx020 缺失「## 维护区」段落。 |
| 黄旗 | mx021 | docs/dispatch/mx/mx021-scheduled-health-probe.md:1 | 已关闭任务卡 mx021 缺失「## 维护区」段落。 |
| 黄旗 | mx022 | docs/dispatch/mx/mx022-opml-import-attribute-order.md:1 | 已关闭任务卡 mx022 缺失「## 维护区」段落。 |
| 黄旗 | mx023 | docs/dispatch/mx/mx023-frontend-coverage-ci-gate.md:1 | 已关闭任务卡 mx023 缺失「## 维护区」段落。 |
| 黄旗 | mx024 | docs/dispatch/mx/mx024-quick-xml-security-upgrade.md:1 | 已关闭任务卡 mx024 缺失「## 维护区」段落。 |
| 黄旗 | mx025 | docs/dispatch/mx/mx025-core-module-coupling-audit.md:1 | 已关闭任务卡 mx025 缺失「## 维护区」段落。 |
| 黄旗 | mx026 | docs/dispatch/mx/mx026-rssservice-websub-p0.md:1 | 已关闭任务卡 mx026 缺失「## 维护区」段落。 |
| 黄旗 | mx027 | docs/dispatch/mx/mx027-core-60.md:1 | 已关闭任务卡 mx027 缺失「## 维护区」段落。 |
| 黄旗 | mx028 | docs/dispatch/mx/mx028-rss-feed-validation-before-add.md:1 | 已关闭任务卡 mx028 缺失「## 维护区」段落。 |
| 黄旗 | mx029 | docs/dispatch/mx/mx029-media-library-sort-persistence.md:1 | 已关闭任务卡 mx029 缺失「## 维护区」段落。 |
| 黄旗 | qb001 | docs/dispatch/qb/qb001-qb-ssot.md:1 | 已关闭任务卡 qb001 缺失「## 维护区」段落。 |
| 黄旗 | qb002 | docs/dispatch/qb/qb002-task.md:1 | 已关闭任务卡 qb002 缺失「## 维护区」段落。 |
| 黄旗 | qb003 | docs/dispatch/qb/qb003-lint.md:1 | 已关闭任务卡 qb003 缺失「## 维护区」段落。 |
| 黄旗 | qb004 | docs/dispatch/qb/qb004-api-response-time-logging.md:1 | 已关闭任务卡 qb004 缺失「## 维护区」段落。 |
| 黄旗 | qb005 | docs/dispatch/qb/qb005-script-argument-parsing-fix.md:1 | 已关闭任务卡 qb005 缺失「## 维护区」段落。 |
| 黄旗 | xy001 | docs/dispatch/xy/xy001-write-video-script-command.md:1 | 已关闭任务卡 xy001 缺失「## 维护区」段落。 |
| 黄旗 | xy002 | docs/dispatch/xy/xy002-bug-scan-and-fix.md:1 | 已关闭任务卡 xy002 缺失「## 维护区」段落。 |
| 黄旗 | xy004 | docs/dispatch/xy/xy004-fix-audio-voice-ducking.md:1 | 已关闭任务卡 xy004 缺失「## 维护区」段落。 |
| 黄旗 | xy005 | docs/dispatch/xy/xy005-fix-audio-bgm-and-level-norm.md:1 | 已关闭任务卡 xy005 缺失「## 维护区」段落。 |
| 黄旗 | xy006 | docs/dispatch/xy/xy006-platform-kuaishou-channels-bridge.md:1 | 已关闭任务卡 xy006 缺失「## 维护区」段落。 |
| 黄旗 | xy007 | docs/dispatch/xy/xy007-bilibili-toutiao-cookie-collector.md:1 | 已关闭任务卡 xy007 缺失「## 维护区」段落。 |
| 黄旗 | xy008 | docs/dispatch/xy/xy008-auto-build-openclaw-plugin.md:1 | 已关闭任务卡 xy008 缺失「## 维护区」段落。 |
| 黄旗 | xy009 | docs/dispatch/xy/xy009-video-pexels-clip-downloader.md:1 | 已关闭任务卡 xy009 缺失「## 维护区」段落。 |
| 黄旗 | xy010 | docs/dispatch/xy/xy010-video-high-bitrate-crf-encoding.md:1 | 已关闭任务卡 xy010 缺失「## 维护区」段落。 |
| 黄旗 | xy011 | docs/dispatch/xy/xy011-subtitle-karaoke-style-ass-rendering.md:1 | 已关闭任务卡 xy011 缺失「## 维护区」段落。 |
| 黄旗 | xy012 | docs/dispatch/xy/xy012-tts-multi-voice-emotion-selector.md:1 | 已关闭任务卡 xy012 缺失「## 维护区」段落。 |
| 黄旗 | xy013 | docs/dispatch/xy/xy013-render-hyperframes-glass-template.md:1 | 已关闭任务卡 xy013 缺失「## 维护区」段落。 |
| 黄旗 | xy014 | docs/dispatch/xy/xy014-eng-baseline-video-pipeline-alignment.md:1 | 已关闭任务卡 xy014 缺失「## 维护区」段落。 |
| 黄旗 | xy015 | docs/dispatch/xy/xy015-eng-profile-renewal-2026-08.md:1 | 已关闭任务卡 xy015 缺失「## 维护区」段落。 |
| 黄旗 | xy016 | docs/dispatch/xy/xy016-video-pipeline-recon-html-report.md:1 | 已关闭任务卡 xy016 缺失「## 维护区」段落。 |
| 黄旗 | xy017 | docs/dispatch/xy/xy017-storage-layout-normalize.md:1 | 已关闭任务卡 xy017 缺失「## 维护区」段落。 |
| 黄旗 | xy018 | docs/dispatch/xy/xy018-config-drift-fix.md:1 | 已关闭任务卡 xy018 缺失「## 维护区」段落。 |
| 黄旗 | xy019 | docs/dispatch/xy/xy019-prod-gap-fix.md:1 | 已关闭任务卡 xy019 缺失「## 维护区」段落。 |
| 黄旗 | xy020 | docs/dispatch/xy/xy020-round2-legacy-inventory.md:1 | 已关闭任务卡 xy020 缺失「## 维护区」段落。 |
| 黄旗 | xy021 | docs/dispatch/xy/xy021-purge-hardcode-old-rules.md:1 | 已关闭任务卡 xy021 缺失「## 维护区」段落。 |
| 黄旗 | xy022 | docs/dispatch/xy/xy022-dynamic-path-derivation.md:1 | 已关闭任务卡 xy022 缺失「## 维护区」段落。 |
| 黄旗 | xy023 | docs/dispatch/xy/xy023-env-credential-alignment.md:1 | 已关闭任务卡 xy023 缺失「## 维护区」段落。 |
| 黄旗 | xy025 | docs/dispatch/xy/xy025-media-quality-acceptance.md:1 | 已关闭任务卡 xy025 缺失「## 维护区」段落。 |
| 黄旗 | xy026 | docs/dispatch/xy/xy026-p0-flow.md:1 | 已关闭任务卡 xy026 缺失「## 维护区」段落。 |
| 黄旗 | xy027 | docs/dispatch/xy/xy027-xianyu-hyperframes.md:1 | 已关闭任务卡 xy027 缺失「## 维护区」段落。 |
| 黄旗 | xy028 | docs/dispatch/xy/xy028-pytest-3.md:1 | 已关闭任务卡 xy028 缺失「## 维护区」段落。 |
| 黄旗 | xy029 | docs/dispatch/xy/xy029-task.md:1 | 已关闭任务卡 xy029 缺失「## 维护区」段落。 |
| 黄旗 | xy030 | docs/dispatch/xy/xy030-video-encoding-progress-log.md:1 | 已关闭任务卡 xy030 缺失「## 维护区」段落。 |
| 黄旗 | xy031 | docs/dispatch/xy/xy031-config-path-resolution-fix.md:1 | 已关闭任务卡 xy031 缺失「## 维护区」段落。 |
| 蓝旗 | T1 | docs/dispatch/T1-server-skeleton.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T1-R | docs/dispatch/T1-R-server-skeleton-deep.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T10 | docs/dispatch/T10-kb-init.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T11 | docs/dispatch/T11-kb-mcp-semantic.md:3 | 卡头「关联」字段 'INT-120（CCC 重构，D3 收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T11-R | docs/dispatch/T11-R-kb-closeout.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T12 | docs/dispatch/T12-legacy-retire-list.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T12-R | docs/dispatch/T12-R-legacy-2017-audit.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T13 | docs/dispatch/T13-server-http-api.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T14 | docs/dispatch/T14-e2e-pipeline-test.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T14-R | docs/dispatch/T14-R-e2e-new-stack.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T15 | docs/dispatch/T15-legacy-retire-exec.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T16 | docs/dispatch/T16-shell-integration-api.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T17 | docs/dispatch/T17-full-acceptance.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T18 | docs/dispatch/T18-phase2-retire-exec.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T19 | docs/dispatch/T19-shell-migration.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T2 | docs/dispatch/T2-engine-core.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T20 | docs/dispatch/T20-board-shell-migration.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T21 | docs/dispatch/T21-ops-shell-migration.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T22 | docs/dispatch/T22-deploy-2017.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T23 | docs/dispatch/T23-http-direct-open.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T24 | docs/dispatch/T24-desktop-repackage-web-chat.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T24-R | docs/dispatch/T24-R-desktop-protocol-align.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T25 | docs/dispatch/T25-restore-legacy-chat.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T26 | docs/dispatch/T26-desktop-backend-refactor.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T26-R | docs/dispatch/T26-R-self-audit-cleanup.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T27 | docs/dispatch/T27-relay-2017-restart.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T28 | docs/dispatch/T28-desktop-repackage.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T29 | docs/dispatch/T29-chat-brain-agent.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T3 | docs/dispatch/T3-board-web.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T3-R | docs/dispatch/T3-R-board-state-normalize.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T30 | docs/dispatch/T30-http-refactor.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收尾）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T31 | docs/dispatch/T31-refactor-closeout-docs-baseline.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收口）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T32 | docs/dispatch/T32-refactor-closeout-engine-real-dispatch.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收口）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T33 | docs/dispatch/T33-refactor-closeout-hardcode-cluster.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收口）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T34 | docs/dispatch/T34-refactor-closeout-deadcode-dual-shell.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收口）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T35 | docs/dispatch/T35-refactor-closeout-hangover-regression.md:3 | 卡头「关联」字段 'INT-120（CCC 重构收口）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T36 | docs/dispatch/T36-m4-kb-seed-refresh.md:3 | 卡头「关联」字段 'INT-120（M4 知识移植/独立移交' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T37 | docs/dispatch/T37-m4-brain-kb.md:3 | 卡头「关联」字段 'INT-120（M4 知识移植/独立移交' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T38 | docs/dispatch/T38-m4-handoff-acceptance.md:3 | 卡头「关联」字段 'INT-120（M4 知识移植/独立移交' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T39 | docs/dispatch/T39-engine-dispatch-by-binding.md:3 | 卡头「关联」字段 'INT-120 关闭后新阶段' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T4 | docs/dispatch/T4-relay-mac2017.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T4-R | docs/dispatch/T4-R-deploy-hardcode-fix.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T40 | docs/dispatch/T40-shell-base-3col-ui.md:3 | 卡头「关联」字段 '新阶段「双壳可用 + 心智升级」（老板 2026-08-03 指示）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T41 | docs/dispatch/T41-brain-mind-streaming.md:3 | 卡头「关联」字段 '新阶段「双壳可用 + 心智升级」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T42 | docs/dispatch/T42-dual-shell-e2e-acceptance.md:3 | 卡头「关联」字段 '新阶段「双壳可用 + 心智升级」收口' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T43 | docs/dispatch/T43-conversation-long-poll.md:3 | 卡头「关联」字段 '新阶段「对话壳感知 + 增量同步」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T44 | docs/dispatch/T44-shell-ux-optimization.md:3 | 卡头「关联」字段 '老板实测反馈「问题太多」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T45 | docs/dispatch/T45-user-centric-ux-overhaul.md:3 | 卡头「关联」字段 '老板实测强烈反馈（2026-08-04）——「登录脱裤子放屁」「发一次就断」「无流式无工具卡」「界面一堆 bug」；Codex 真机取证逐项定位根因' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T46 | docs/dispatch/T46-conversation-stability-sse.md:3 | 卡头「关联」字段 '老板实测反馈（2026-08-04）「对话过程中切换界面就中断」「思考过程/思考文字没展示」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T47 | docs/dispatch/T47-project-thread-sidebar.md:3 | 卡头「关联」字段 '老板指出「左侧栏展示逻辑错误——应该项目+对话，用项目区分，不是任务分组；展示逻辑借鉴 Codex/Cursor 成熟工具」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T48 | docs/dispatch/T48-shell-problem-audit.md:3 | 卡头「关联」字段 '老板反馈「桌面端和 HTTP 页面小问题非常多」+「展示逻辑借鉴 Codex/Cursor 成熟工具」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T49 | docs/dispatch/T49-conversation-as-workflow.md:3 | 卡头「关联」字段 '老板指示「站在业务流程梳理高度，前端界面与后端功能业务打通」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T5 | docs/dispatch/T5-board-schedule.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T50 | docs/dispatch/T50-dual-shell-e2e-acceptance.md:3 | 卡头「关联」字段 '业务流程打通收口' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T51 | docs/dispatch/T51-knowledge-mcp-optimize.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T52 | docs/dispatch/T52-automation-base.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T53 | docs/dispatch/T53-console-roadmap-fix.md:3 | 卡头「关联」字段 '阶段 3（控制台/线路图修复，老板 2026-08-04）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T54 | docs/dispatch/T54-auto-naming-migration.md:3 | 卡头「关联」字段 '阶段 3（T-A1 命名规则落地，Codex 决策 2026-08-04）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T55 | docs/dispatch/T55-index-layer.md:3 | 卡头「关联」字段 '阶段 3（T-A2 索引层，过夜任务后端链 1/3）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T56 | docs/dispatch/T56-card-components.md:3 | 卡头「关联」字段 '阶段 3（T-B1 统一卡片组件，过夜任务前端链 1/2）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T57 | docs/dispatch/T57-big-small-cards.md:3 | 卡头「关联」字段 '阶段 3（T-A4，过夜任务后端链 2/3）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T58 | docs/dispatch/T58-board-refactor.md:3 | 卡头「关联」字段 '阶段 3（T-B2，过夜任务前端链 2/2）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T59 | docs/dispatch/T59-engine-parallel-relay-guard.md:3 | 卡头「关联」字段 '过夜任务发现——① Engine 串行派发（同步等执行体完成才派下一张）；② 上游中继多次波动导致执行卡死/超时' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T6 | docs/dispatch/T6-roadmap-p3.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T60 | docs/dispatch/T60-console-cockpit.md:3 | 卡头「关联」字段 '前端四板块架构（T-B3）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T61 | docs/dispatch/T61-task-flow-linked.md:3 | 卡头「关联」字段 '前端四板块架构（T-B4）+ T49 对话即工作' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T62 | docs/dispatch/T62-archive-review.md:3 | 卡头「关联」字段 '阶段 3（T-A5）+ T50 联调发现（/cards 缺索引返回空，需兜底）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T63 | docs/dispatch/T63-nginx-entry.md:3 | 卡头「关联」字段 '阶段 3（Nginx 统一入口）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T64 | docs/dispatch/T64-engine-auto-worktree.md:3 | 卡头「关联」字段 'T59 并行派发发现——每卡需独立 worktree，当前靠卡内续作指令手动建' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T65 | docs/dispatch/T65-dual-shell-align.md:3 | 卡头「关联」字段 '前端四板块架构（T-B5 双壳对齐）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T66 | docs/dispatch/T66-card-format-debt.md:3 | 卡头「关联」字段 '任务卡体系规则（旧卡 69 处格式偏差规范化）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T67 | docs/dispatch/T67-deploy-race-guard.md:3 | 卡头「关联」字段 'T60 误派复盘（2026-08-05 部署窗口：已验收卡因卡头未同步被 Engine 重新拉起）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T68 | docs/dispatch/T68-http-resource-resilience.md:3 | 卡头「关联」字段 'T48 审计 P0（M1→2017 静态资源并发 ERR_CONNECTION_RESET 41%，SPA 白屏根因，前端侧）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T69 | docs/dispatch/T69-release-engine-plist-rebuild.md:3 | 卡头「关联」字段 'T68 部署事故（2026-08-05：start_engine 遇 plist 缺失仅 WARN，Engine 掉线未恢复，Codex 现场重建恢复）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T7 | docs/dispatch/T7-ops-timer-p4.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T70 | docs/dispatch/T70-code-audit.md:3 | 卡头「关联」字段 '老板 2026-08-06 指示「Cursor 做一次全部 CCC 项目检查，主要做代码 bug 检查」' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T71 | docs/dispatch/T71-fix-server-p0.md:3 | 卡头「关联」字段 'T70 审计 P0（F01 卡头替换误改正文 / F02 非 UTF-8 卡拖垮扫描 / F11 SSE 断流不 settle）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T72 | docs/dispatch/T72-fix-desktop-p0.md:3 | 卡头「关联」字段 'T70 审计 P0（F18 workspace 传路径 / F19 Kanban 英文旧列 / F20 流式缺 thread_id/model）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T76 | docs/dispatch/T76-conversation-base-hardening.md:3 | 卡头「关联」字段 '对话大底座加固（F16）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T8 | docs/dispatch/T8-switch-checklist.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T8-X | docs/dispatch/T8-X-execute-switch.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | T9 | docs/dispatch/T9-kb-seed.md:3 | 卡头「关联」字段 'INT-120（CCC 重构）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc001 | docs/dispatch/ccc/ccc001-e2e-smoke-engine-dirty.md:3 | 卡头「关联」字段 'E2E联调 2026-08-06' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc002 | docs/dispatch/ccc/ccc002-e2e-smoke-opencode.md:3 | 卡头「关联」字段 'E2E联调 OpenCode 2026-08-06' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc003 | docs/dispatch/ccc/ccc003-engine-anti-fake-success-and-template-align.md:3 | 卡头「关联」字段 'E2E联调技术债 2026-08-06' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc004 | docs/dispatch/ccc/ccc004-register-ccc-demo-prefix.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc005 | docs/dispatch/ccc/ccc005-registry-single-source.md:3 | 卡头「关联」字段 '文档与项目注册统一治理' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc006 | docs/dispatch/ccc/ccc006-engine-audit-auto-backfill.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc007 | docs/dispatch/ccc/ccc007-m5-audit-dogfood-rebase-hint.md:3 | 卡头「关联」字段 'M5 真机审狗粮' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc008 | docs/dispatch/ccc/ccc008-ready-probe-script.md:3 | 卡头「关联」字段 'ccc-plan: M7 ready-probe dogfood' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc009 | docs/dispatch/ccc/ccc009-stale-docs-archive-cleanup.md:3 | 卡头「关联」字段 'ccc-plan: 文档卫生与业务总线路图' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc010 | docs/dispatch/ccc/ccc010-roadmap-business-track-xy.md:3 | 卡头「关联」字段 'ccc-plan: 文档卫生与业务总线路图' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc012 | docs/dispatch/ccc/ccc012-48-codex.md:3 | 卡头「关联」字段 '升级批次 3 生命周期' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc013 | docs/dispatch/ccc/ccc013-flow-verify-pipeline.md:3 | 卡头「关联」字段 'CCC 系统化升级' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc014 | docs/dispatch/ccc/ccc014-converge-stale-remote-branches.md:3 | 卡头「关联」字段 'CCC 治理' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc015 | docs/dispatch/ccc/ccc015-gate-audit-separation.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc016 | docs/dispatch/ccc/ccc016-t73-t70-p1-11.md:3 | 卡头「关联」字段 'INT-129' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc017 | docs/dispatch/ccc/ccc017-prompt.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc018 | docs/dispatch/ccc/ccc018-task.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc019 | docs/dispatch/ccc/ccc019-engine-gate-skip-metrics.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc020 | docs/dispatch/ccc/ccc020-prompt-injection-dashboard.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | ccc021 | docs/dispatch/ccc/ccc021-s8.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | clw007 | docs/dispatch/clw/clw007-resume-cwd-fix.md:3 | 卡头「关联」字段 'ccc-plan: clw007 会话恢复工作目录 + 小缺陷修复' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp001 | docs/dispatch/hp/hp001-recon-baseline-roadmap.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp002 | docs/dispatch/hp/hp002-monitoring-git-probe.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp003 | docs/dispatch/hp/hp003-backup-alignment.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp004 | docs/dispatch/hp/hp004-collector-source-expansion.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp005 | docs/dispatch/hp/hp005-frontend-fake-data-contract.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp006 | docs/dispatch/hp/hp006-search-quality-short-chunks.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp007 | docs/dispatch/hp/hp007-cli-fulltext-and-short-chunk-gate.md:3 | 卡头「关联」字段 'ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp008 | docs/dispatch/hp/hp008-project-id-mapping-plan.md:3 | 卡头「关联」字段 'ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp010 | docs/dispatch/hp/hp010-collector-multisource-fix.md:3 | 卡头「关联」字段 'ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp011 | docs/dispatch/hp/hp011-qb-docs-ownership-fix.md:3 | 卡头「关联」字段 'ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp012 | docs/dispatch/hp/hp012-dashboard-search-real-data.md:3 | 卡头「关联」字段 'ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp013 | docs/dispatch/hp/hp013-library-doc-activity-notes-real-data.md:3 | 卡头「关联」字段 'ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp014 | docs/dispatch/hp/hp014-backend-export-library-count.md:3 | 卡头「关联」字段 'ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp015 | docs/dispatch/hp/hp015-frontend-page-test-coverage.md:3 | 卡头「关联」字段 'ccc-plan: HP 前端测试覆盖补齐（页面渲染 + 关键交互，目标测试评分 4→7）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp016 | docs/dispatch/hp/hp016-collector-pipeline-repair.md:3 | 卡头「关联」字段 'ccc-plan: HP 采集管道完整性修复（ingest/md_parser 恢复 + 解析 bug + ccc-docs 补采）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp017 | docs/dispatch/hp/hp017-chunk-hp007.md:3 | 卡头「关联」字段 'hp007 遗留：存量 445 短 chunk 处理方案落库' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp018 | docs/dispatch/hp/hp018-hp-pg-backtest-cron.md:3 | 卡头「关联」字段 'INT-075' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp019 | docs/dispatch/hp/hp019-task.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp020 | docs/dispatch/hp/hp020-chunk.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp021 | docs/dispatch/hp/hp021-search-result-relevance-scoring-display.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | hp022 | docs/dispatch/hp/hp022-collector-network-error-retry.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx001 | docs/dispatch/mx/mx001-recon-and-baseline.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx002 | docs/dispatch/mx/mx002-add-server-health-api-and-python-smoke-test.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx003 | docs/dispatch/mx/mx003-recon-business-tracks.md:3 | 卡头「关联」字段 'mx 业务线路摸底' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx004 | docs/dispatch/mx/mx004-service-health-probe.md:3 | 卡头「关联」字段 'ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx005 | docs/dispatch/mx/mx005-polish-inventory.md:3 | 卡头「关联」字段 'ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx006 | docs/dispatch/mx/mx006-cargo-fmt-ci-gate.md:3 | 卡头「关联」字段 'ccc-plan: mx 打磨第一批：后端格式门禁 + 设置页路径校验' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx007 | docs/dispatch/mx/mx007-settings-path-frontend-validation.md:3 | 卡头「关联」字段 'ccc-plan: mx 打磨第一批：后端格式门禁 + 设置页路径校验' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx008 | docs/dispatch/mx/mx008-http-page-ux-audit.md:3 | 卡头「关联」字段 'ccc-plan: HTTP 页面体验巡检：RSS 优先 + 全页面代码/显示/双端适配' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx009 | docs/dispatch/mx/mx009-atom-parser-library.md:3 | 卡头「关联」字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx010 | docs/dispatch/mx/mx010-opml-export-bearer-auth.md:3 | 卡头「关联」字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx011 | docs/dispatch/mx/mx011-tablet-breakpoint-layout-fix.md:3 | 卡头「关联」字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx012 | docs/dispatch/mx/mx012-rss-stats-backend-aggregation.md:3 | 卡头「关联」字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx013 | docs/dispatch/mx/mx013-architecture-doc-dev-guide.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx014 | docs/dispatch/mx/mx014-crawl-all-image-localization.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx015 | docs/dispatch/mx/mx015-crawl-all-error-writeback.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx016 | docs/dispatch/mx/mx016-pc-keyboard-shortcuts.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx017 | docs/dispatch/mx/mx017-rss-image-proxy.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx018 | docs/dispatch/mx/mx018-rss-reader-css-class.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx019 | docs/dispatch/mx/mx019-backend-coverage-core-tests.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx020 | docs/dispatch/mx/mx020-rss-save-transaction.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx021 | docs/dispatch/mx/mx021-scheduled-health-probe.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx022 | docs/dispatch/mx/mx022-opml-import-attribute-order.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx023 | docs/dispatch/mx/mx023-frontend-coverage-ci-gate.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx024 | docs/dispatch/mx/mx024-quick-xml-security-upgrade.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx025 | docs/dispatch/mx/mx025-core-module-coupling-audit.md:3 | 卡头「关联」字段 'ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx026 | docs/dispatch/mx/mx026-rssservice-websub-p0.md:3 | 卡头「关联」字段 'mx025 架构问题清单 #1 P0' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx027 | docs/dispatch/mx/mx027-core-60.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx028 | docs/dispatch/mx/mx028-rss-feed-validation-before-add.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | mx029 | docs/dispatch/mx/mx029-media-library-sort-persistence.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | qb001 | docs/dispatch/qb/qb001-qb-ssot.md:3 | 卡头「关联」字段 'INT-121' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | qb002 | docs/dispatch/qb/qb002-task.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | qb003 | docs/dispatch/qb/qb003-lint.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | qb004 | docs/dispatch/qb/qb004-api-response-time-logging.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | qb005 | docs/dispatch/qb/qb005-script-argument-parsing-fix.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy001 | docs/dispatch/xy/xy001-write-video-script-command.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy002 | docs/dispatch/xy/xy002-bug-scan-and-fix.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy003 | docs/dispatch/xy/xy003-wire-2pass-encoding.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy004 | docs/dispatch/xy/xy004-fix-audio-voice-ducking.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy005 | docs/dispatch/xy/xy005-fix-audio-bgm-and-level-norm.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy006 | docs/dispatch/xy/xy006-platform-kuaishou-channels-bridge.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy007 | docs/dispatch/xy/xy007-bilibili-toutiao-cookie-collector.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy008 | docs/dispatch/xy/xy008-auto-build-openclaw-plugin.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy009 | docs/dispatch/xy/xy009-video-pexels-clip-downloader.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy010 | docs/dispatch/xy/xy010-video-high-bitrate-crf-encoding.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy011 | docs/dispatch/xy/xy011-subtitle-karaoke-style-ass-rendering.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy012 | docs/dispatch/xy/xy012-tts-multi-voice-emotion-selector.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy013 | docs/dispatch/xy/xy013-render-hyperframes-glass-template.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy014 | docs/dispatch/xy/xy014-eng-baseline-video-pipeline-alignment.md:3 | 卡头「关联」字段 'ccc-plan: xianyu 工程化底座补齐' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy015 | docs/dispatch/xy/xy015-eng-profile-renewal-2026-08.md:3 | 卡头「关联」字段 'ccc-plan: xianyu 工程化底座补齐' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy016 | docs/dispatch/xy/xy016-video-pipeline-recon-html-report.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy017 | docs/dispatch/xy/xy017-storage-layout-normalize.md:3 | 卡头「关联」字段 'ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy018 | docs/dispatch/xy/xy018-config-drift-fix.md:3 | 卡头「关联」字段 'ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy019 | docs/dispatch/xy/xy019-prod-gap-fix.md:3 | 卡头「关联」字段 'ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy020 | docs/dispatch/xy/xy020-round2-legacy-inventory.md:3 | 卡头「关联」字段 'ccc-plan: xy 第二轮历史遗留排查（根基立稳）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy021 | docs/dispatch/xy/xy021-purge-hardcode-old-rules.md:3 | 卡头「关联」字段 'ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy022 | docs/dispatch/xy/xy022-dynamic-path-derivation.md:3 | 卡头「关联」字段 'ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy023 | docs/dispatch/xy/xy023-env-credential-alignment.md:3 | 卡头「关联」字段 'ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy025 | docs/dispatch/xy/xy025-media-quality-acceptance.md:3 | 卡头「关联」字段 'ccc-plan: xy PRM 批3：成片质量验收联测 + 关卡自动验证脚本' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy026 | docs/dispatch/xy/xy026-p0-flow.md:3 | 卡头「关联」字段 'xy PRM P0-FLOW 前置（xy024 意图重建）' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy027 | docs/dispatch/xy/xy027-xianyu-hyperframes.md:3 | 卡头「关联」字段 'INT-122' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy028 | docs/dispatch/xy/xy028-pytest-3.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy029 | docs/dispatch/xy/xy029-task.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy030 | docs/dispatch/xy/xy030-video-encoding-progress-log.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |
| 蓝旗 | xy031 | docs/dispatch/xy/xy031-config-path-resolution-fix.md:3 | 卡头「关联」字段 '阶段 3 P1' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。 |

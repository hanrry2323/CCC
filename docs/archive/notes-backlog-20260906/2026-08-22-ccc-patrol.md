# 巡查风险报告 — 2026-08-22-ccc-patrol

> 采集时间: 2026-08-22T02:18:27.220841 · 发现数: 8

## 风险发现列表（按权重降序排序）

| 权重 (Weight) | 交叉确认 (Cross-Confirm) | 影响 (Impact) | 频次 (Frequency) | 描述 (Title) | 项目 (Project) | 作用对象 (Acting On) | 证据 (Evidence) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.00 | 0.5 | 4 | 4 | 方案 cla-plan-003 关联了不存在的任务卡: eba676 | cla | `docs/projects/cla/plans/003-debt-cleanup.md` | `docs/projects/cla/plans/003-debt-cleanup.md:1` |
| 3.00 | 0.5 | 3 | 2 | 项目 cla 缺席 roadmap.md 的业务线路段落 | cla | `docs/roadmap.md` | `docs/roadmap.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 mx-plan-004 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | mx | `docs/projects/mx/plans/004-public-migration-and-multitarget-cicd.md` | `docs/projects/mx/plans/004-public-migration-and-multitarget-cicd.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 mx-plan-005 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | mx | `docs/projects/mx/plans/005-opml-import-fix.md` | `docs/projects/mx/plans/005-opml-import-fix.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 mx-plan-006 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | mx | `docs/projects/mx/plans/006-opml-export-auth.md` | `docs/projects/mx/plans/006-opml-export-auth.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 mx-plan-008 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | mx | `docs/projects/mx/plans/008-coverage-expansion.md` | `docs/projects/mx/plans/008-coverage-expansion.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 qb-plan-002 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | qb | `docs/projects/qb/plans/002-strategy-core-unify.md` | `docs/projects/qb/plans/002-strategy-core-unify.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 qb-plan-003 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | qb | `docs/projects/qb/plans/003-backtest-triconverge.md` | `docs/projects/qb/plans/003-backtest-triconverge.md:1` |

## 建议转卡命令

> 巡查 Agent 仅打印建议出卡命令，绝不自动出卡/自动合入。

- 针对 `plan_ref_missing_cards_cla-plan-003`:
  ```bash
  scripts/new-card.sh --project cla --title "修复：方案 cla-plan-003 关联了不存在的任务卡: eba676" --related "patrol: 2026-08-22-ccc-patrol"
  ```
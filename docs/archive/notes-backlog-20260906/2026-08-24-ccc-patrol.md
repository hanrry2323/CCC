# 巡查风险报告 — 2026-08-24-ccc-patrol

> 采集时间: 2026-08-24T23:54:30.294581 · 发现数: 9

## 风险发现列表（按权重降序排序）

| 权重 (Weight) | 交叉确认 (Cross-Confirm) | 影响 (Impact) | 频次 (Frequency) | 描述 (Title) | 项目 (Project) | 作用对象 (Acting On) | 证据 (Evidence) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.00 | 0.5 | 4 | 4 | 方案 cla-plan-003 关联了不存在的任务卡: eba676 | cla | `docs/projects/cla/plans/003-debt-cleanup.md` | `docs/projects/cla/plans/003-debt-cleanup.md:1` |
| 3.00 | 0.5 | 3 | 2 | 项目 cla 缺席 roadmap.md 的业务线路段落 | cla | `docs/roadmap.md` | `docs/roadmap.md:1` |
| 3.00 | 0.5 | 3 | 2 | 项目 tst 缺席 roadmap.md 的业务线路段落 | tst | `docs/roadmap.md` | `docs/roadmap.md:1` |
| 3.00 | 0.5 | 3 | 2 | 里程碑 mx/M8 · 媒体库与 RSS 阅读体验优化 进度不一致：声明 进行中，实际完成率 100%（4/4 方案 → 已完成） | mx | `docs/projects/mx/roadmap.md` | `docs/projects/mx/roadmap.md:1` |
| 3.00 | 0.5 | 3 | 2 | 方案 tst-plan-001 进度不一致：声明 1/2，实际 1/3（级联回写滞后或卡状态变动） | tst | `docs/projects/tst/plans/001-pipeline-smoke.md` | `docs/projects/tst/plans/001-pipeline-smoke.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 mx-plan-004 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | mx | `docs/projects/mx/plans/004-public-migration-and-multitarget-cicd.md` | `docs/projects/mx/plans/004-public-migration-and-multitarget-cicd.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 qb-plan-002 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | qb | `docs/projects/qb/plans/002-strategy-core-unify.md` | `docs/projects/qb/plans/002-strategy-core-unify.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 qb-plan-003 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | qb | `docs/projects/qb/plans/003-backtest-triconverge.md` | `docs/projects/qb/plans/003-backtest-triconverge.md:1` |
| 2.00 | 0.5 | 2 | 2 | 方案 xy-plan-008 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化） | xy | `docs/projects/xy/plans/008-high-expression-v2.md` | `docs/projects/xy/plans/008-high-expression-v2.md:1` |

## 建议转卡命令

> 巡查 Agent 仅打印建议出卡命令，绝不自动出卡/自动合入。

- 针对 `plan_ref_missing_cards_cla-plan-003`:
  ```bash
  scripts/new-card.sh --project cla --title "修复：方案 cla-plan-003 关联了不存在的任务卡: eba676" --related "patrol: 2026-08-24-ccc-patrol"
  ```
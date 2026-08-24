# 巡查风险报告 — 2026-08-16-ccc-patrol

> 采集时间: 2026-08-16T20:15:10.096858 · 发现数: 2

## 风险发现列表（按权重降序排序）

| 权重 (Weight) | 交叉确认 (Cross-Confirm) | 影响 (Impact) | 频次 (Frequency) | 描述 (Title) | 项目 (Project) | 作用对象 (Acting On) | 证据 (Evidence) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3.00 | 0.5 | 3 | 2 | 里程碑 xy/a 进度不一致 | xy | `docs/projects/xy/roadmap.md` | `docs/projects/xy/roadmap.md:1` |
| 3.00 | 0.5 | 2 | 3 | xy001 状态漂移 | xy | `x` | `x:1` |

## 建议转卡命令

> 巡查 Agent 仅打印建议出卡命令，绝不自动出卡/自动合入。

- 针对 `milestone_progress_xy_a`:
  ```bash
  scripts/new-card.sh --project xy --title "修复：里程碑 xy/a 进度不一致" --related "patrol: 2026-08-16-ccc-patrol"
  ```
- 针对 `status_drift_xy001`:
  ```bash
  scripts/new-card.sh --project xy --title "修复：xy001 状态漂移" --related "patrol: 2026-08-16-ccc-patrol"
  ```
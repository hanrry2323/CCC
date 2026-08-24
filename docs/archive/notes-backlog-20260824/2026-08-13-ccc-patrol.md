# 巡查风险报告 — 2026-08-13-ccc-patrol

> 采集时间: 2026-08-13T18:40:04.275239 · 发现数: 2

## 风险发现列表（按权重降序排序）

| 权重 (Weight) | 交叉确认 (Cross-Confirm) | 影响 (Impact) | 频次 (Frequency) | 描述 (Title) | 项目 (Project) | 作用对象 (Acting On) | 证据 (Evidence) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3.00 | 0.5 | 2 | 3 | 任务卡 clw004 状态漂移：roadmap.md 标注「⚠️ 未合入 main（分支孤岛，v0.1.0 无此功能）」，但看板/卡文件实际状态为「已关闭」 | clw | `docs/roadmap.md` | `docs/roadmap.md:444` |
| 3.00 | 0.5 | 2 | 3 | 任务卡 clw005 状态漂移：roadmap.md 标注「⚠️ 未合入 main（分支孤岛，v0.1.0 无此功能）」，但看板/卡文件实际状态为「已关闭」 | clw | `docs/roadmap.md` | `docs/roadmap.md:445` |

## 建议转卡命令

> 巡查 Agent 仅打印建议出卡命令，绝不自动出卡/自动合入。

- 针对 `status_drift_clw004`:
  ```bash
  scripts/new-card.sh --project clw --title "修复：任务卡 clw004 状态漂移：roadmap.md 标注「⚠️ 未合入 main（分支孤岛，v0.1.0 无此功能）」，但看板/卡文件实际状态为「已关闭」" --related "patrol: 2026-08-13-ccc-patrol"
  ```
- 针对 `status_drift_clw005`:
  ```bash
  scripts/new-card.sh --project clw --title "修复：任务卡 clw005 状态漂移：roadmap.md 标注「⚠️ 未合入 main（分支孤岛，v0.1.0 无此功能）」，但看板/卡文件实际状态为「已关闭」" --related "patrol: 2026-08-13-ccc-patrol"
  ```
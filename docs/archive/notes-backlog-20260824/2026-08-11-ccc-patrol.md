# 巡查风险报告 — 2026-08-11-ccc-patrol

> 采集时间: 2026-08-11T20:27:09.051281 · 发现数: 6

## 风险发现列表（按权重降序排序）

| 权重 (Weight) | 交叉确认 (Cross-Confirm) | 影响 (Impact) | 频次 (Frequency) | 描述 (Title) | 项目 (Project) | 作用对象 (Acting On) | 证据 (Evidence) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3.00 | 0.5 | 3 | 2 | 项目 cd 缺席 roadmap.md 的业务线路段落 | cd | `docs/roadmap.md` | `docs/roadmap.md:1` |
| 3.00 | 0.5 | 2 | 3 | 任务卡 clw001 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」 | clw | `docs/roadmap.md` | `docs/roadmap.md:441` |
| 3.00 | 0.5 | 2 | 3 | 任务卡 clw002 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」 | clw | `docs/roadmap.md` | `docs/roadmap.md:442` |
| 3.00 | 0.5 | 2 | 3 | 任务卡 clw003 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」 | clw | `docs/roadmap.md` | `docs/roadmap.md:443` |
| 3.00 | 0.5 | 2 | 3 | 任务卡 clw006 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」 | clw | `docs/roadmap.md` | `docs/roadmap.md:446` |
| 3.00 | 0.5 | 2 | 3 | 任务卡 clw007 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」 | clw | `docs/roadmap.md` | `docs/roadmap.md:447` |

## 建议转卡命令

> 巡查 Agent 仅打印建议出卡命令，绝不自动出卡/自动合入。

- 针对 `missing_roadmap_section_cd`:
  ```bash
  scripts/new-card.sh --project cd --title "修复：项目 cd 缺席 roadmap.md 的业务线路段落" --related "patrol: 2026-08-11-ccc-patrol"
  ```
- 针对 `status_drift_clw001`:
  ```bash
  scripts/new-card.sh --project clw --title "修复：任务卡 clw001 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」" --related "patrol: 2026-08-11-ccc-patrol"
  ```
- 针对 `status_drift_clw002`:
  ```bash
  scripts/new-card.sh --project clw --title "修复：任务卡 clw002 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」" --related "patrol: 2026-08-11-ccc-patrol"
  ```
- 针对 `status_drift_clw003`:
  ```bash
  scripts/new-card.sh --project clw --title "修复：任务卡 clw003 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」" --related "patrol: 2026-08-11-ccc-patrol"
  ```
- 针对 `status_drift_clw006`:
  ```bash
  scripts/new-card.sh --project clw --title "修复：任务卡 clw006 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」" --related "patrol: 2026-08-11-ccc-patrol"
  ```
- 针对 `status_drift_clw007`:
  ```bash
  scripts/new-card.sh --project clw --title "修复：任务卡 clw007 状态漂移：roadmap.md 标注「已交付」，但看板/卡文件实际状态为「已关闭」" --related "patrol: 2026-08-11-ccc-patrol"
  ```
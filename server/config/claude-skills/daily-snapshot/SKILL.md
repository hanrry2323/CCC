---
name: daily-snapshot
description: "Run '跑一下今天的情况' or '今天有什么变更' to trigger daily git scan across all projects, get a summary of today's changes, and auto-dispatch drivable items to LoopEngine"
---

# Daily Git Snapshot

Trigger a daily scan of all git projects, receive a structured summary,
and automatically dispatch self-drivable changes to the execution pipeline.

## When to use

- "今天有什么变更"
- "跑一下今天的情况"
- "今日扫描"
- "看看今天各项目的进展"
- "有什么需要我确认的"

## How it works

1. Calls `POST /api/daily-snapshot/dispatch`
2. Backend scans git log since last snapshot for all registered projects
3. Each commit is classified:
   - **auto** — test-only, docs-only, simple fixes → auto-dispatched to LoopEngine
   - **review** — API changes, new features, cross-module → added to boss decision list
   - **decision** — dependency changes → added to boss decision list with ⚠ flag
4. Reports the results back

## Output format

Present results in this structure:
- **Total**: N commits across M active projects
- **Auto-dispatched**: N items (已自动投递执行)
- **Needs review**: N items (请看决策列表)
- **Needs decision**: N items (需你拍板)

For each active project, list: project name, commit count, and counts per category.

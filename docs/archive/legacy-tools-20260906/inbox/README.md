# Inbox — 外部顾问提案（人审采纳门）

> Hub-Shell Phase4。**默认不进 Engine backlog**；须 Desktop/API **采纳**后才 `transfer`。

## 目录

```text
inbox/           # 待采纳 *.md
inbox/adopted/   # 已采纳归档
inbox/README.md  # 本文
```

## 提案文件格式

```markdown
---
project: ccc-demo
title: 短标题
action: transfer
status: pending
pipeline: dev
complexity: small
executor_intent: python
acceptance: 验收一条|验收二条
---

正文作为 plan / goal 来源。
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/desktop/proposals` | 列表（默认仅 pending） |
| POST | `/api/desktop/proposals/{id}/adopt` | 采纳 → transfer |

未采纳时看板不应出现对应 epic。

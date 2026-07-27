# CCC 开发指令包（dev-packets）

给**个人 Claude Code CLI**（接 Relay `flash`）用的可转发任务卡。  
**合入与审测只认 Cursor。** Desktop 对话 Agent 不要跑这些包。

**偏好**：大包多 Phase、一次做完再回报（见 `008-…`），少跑碎卡片。

## 人怎么用

1. 打开一张 `NNN-*.md`，**整份复制**发给 Claude Code。  
2. Claude Code 在仓根按「分支 / 白名单」改；跑「验收」。  
3. 把 `git diff` / 分支名发回 Cursor 会话。  
4. Cursor 审 → 合入或打回修正包。

## Cursor 怎么写新包

复制 [`_TEMPLATE.md`](./_TEMPLATE.md)，填满 8 块；放入本目录；在 [`../briefs/2026-07-27-ccc-production-readiness.md`](../briefs/2026-07-27-ccc-production-readiness.md) 程表挂上 id。

## 包清单

| ID | 文件 | 状态 |
|----|------|------|
| template | [`_TEMPLATE.md`](./_TEMPLATE.md) | 模板 |
| ops-p1-copy-vs-handoff | [`001-ops-p1-copy-vs-handoff.md`](./001-ops-p1-copy-vs-handoff.md) | **已合入** |
| ops-p1-tunnel-row | [`002-ops-p1-tunnel-row.md`](./002-ops-p1-tunnel-row.md) | **已合入** `956d579` |
| ops-p1-domain-chips | [`003-ops-p1-domain-chips.md`](./003-ops-p1-domain-chips.md) | **已合入** `3755224` |
| ops-p1-upstream-panel | [`004-ops-p1-upstream-panel.md`](./004-ops-p1-upstream-panel.md) | **已合入** `0589a94` |
| ops-p2-agent-minds | [`005-ops-p2-agent-minds.md`](./005-ops-p2-agent-minds.md) | **已合入** `fc37932` |
| ops-p2-local-patrol-alerts | [`006-ops-p2-local-patrol-alerts.md`](./006-ops-p2-local-patrol-alerts.md) | **已合入** `ec73900` |
| ops-p2-web-ops-redirect | [`007-ops-p2-web-ops-redirect.md`](./007-ops-p2-web-ops-redirect.md) | **已合入** `c67e079` |
| prod-batch-hub-desktop-polish | [`008-prod-batch-hub-desktop-polish.md`](./008-prod-batch-hub-desktop-polish.md) | 待跑（**大包三 Phase**） |

权威例外：[`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「个人 Claude Code 草稿工」。

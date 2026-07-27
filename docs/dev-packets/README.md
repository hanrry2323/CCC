# CCC 开发指令包（dev-packets）

给**个人 Claude Code CLI**（接 Relay `flash`）用的可转发任务卡。  
**合入与审测只认 Cursor。** Desktop 对话 Agent 不要跑这些包。

**偏好**：大包多 Phase、一次做完再回报，少跑碎卡片。  
**主题纪律（2026-07-27）**：Ops/壳抛光主路径 **已收束**。009 为文档/SPA 收尾；**其后草稿工只接金路径断点的白名单缺陷包**（见 [`../briefs/2026-07-27-ccc-production-readiness.md`](../briefs/2026-07-27-ccc-production-readiness.md)）。UI chip / 停更页类包 **不再新开**，除非金路径证据明确指向该文件。

## 人怎么用

1. 打开一张 `NNN-*.md`，**整份复制**发给 Claude Code。  
2. Claude Code 在仓根按「分支 / 白名单」改；跑「验收」。  
3. 把 `git diff` / 分支名发回 Cursor 会话。  
4. Cursor 审 → 合入或打回修正包。

## Cursor 怎么写新包

复制 [`_TEMPLATE.md`](./_TEMPLATE.md)，填满 8 块；放入本目录；在 production-readiness brief 程表挂上 id。  
**新包默认类型** = 金路径修复（Engine/门禁/探针/双机可观测的白名单文件），不是运维 UI 抛光。

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
| prod-batch-hub-desktop-polish | [`008-prod-batch-hub-desktop-polish.md`](./008-prod-batch-hub-desktop-polish.md) | **已合入** `d0c601c`（大包三 Phase） |
| prod-batch-docs-spa-cleanup | [`009-prod-batch-docs-spa-cleanup.md`](./009-prod-batch-docs-spa-cleanup.md) | **已合入**（壳收尾完成；Ops 抛光主路径结束） |
| golden-path-kb-script-seed | [`010-golden-path-kb-script-seed.md`](./010-golden-path-kb-script-seed.md) | **待 Claude 草稿**（kb 每 tick + verified→testing + script_seed 勿抢 opencode） |

权威例外：[`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「个人 Claude Code 草稿工」。  
三层出门 / 金路径：[`../briefs/2026-07-27-ccc-production-readiness.md`](../briefs/2026-07-27-ccc-production-readiness.md) · [`../briefs/2026-07-27-golden-path-evidence.md`](../briefs/2026-07-27-golden-path-evidence.md)。

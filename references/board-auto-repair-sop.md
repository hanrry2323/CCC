# 看板自动修复 SOP（Agent / 钩子）

> **权威**：`docs/product/loop-engineer-authority.md`「编排自愈硬指标」  
> **触发**：编排异常（abnormal/failed/stopLoss）、`pending_no_fanout`、Engine 未消费  
> **禁止**：invent；自动 `intent_stable`；教老板手点「复制给对话」；写业务源码；对 CCC orch 投业务 epic

## 固定顺序

1. `hub_repair(status)`（可带 `project_id`）→ 看 abnormal / failed_epics / stuck_running / pending_no_fanout  
2. Engine 未跑或未 enabled → 走已有 wake / `task_dispatch` 路径（**不 invent**）  
3. `hub_repair(clear_blockers)` → 归档可清残卡 + 沉底孤儿 running + purge flow 幽灵 + wake  
4. 可恢复 work → `hub_repair(reopen)` **一次**；permanent / 需改意图 → **停**，升红 + `copy_payload`（给人改意图，不是日常清板）  
5. `pending_no_fanout` → 确认已 wake；若平台未自动重扇出，报告阻塞因；禁止空转卫生 epic  
6. 人话回报：清了几张、当前 counts、是否已再 wake；正文禁 outbox/Terminal 教程

## 自动钩子文案模板（Desktop / sidecar）

```text
【编排自愈 · 自动 SOP · 勿问老板】
项目：{project_id}
大卡：{epic_id}
摘要：{hint}
请严格按 references/board-auto-repair-sop.md：
hub_repair(status) → clear_blockers → 必要 reopen 一次 → 回报板面数字。
禁止甩锅让老板复制/去运维页；禁止 invent；禁止写业务源码。
```

## 冷却

同一 `project_id|epic_id` 自动注入 ≤1 次 / 会话窗；未清干净 → 红灯通知，不无限刷 Agent。

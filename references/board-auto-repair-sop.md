# 看板自动修复 SOP（Agent / 钩子）

> **权威**：`docs/product/loop-engineer-authority.md`「编排自愈硬指标」  
> **触发**：编排异常（abnormal/failed/stopLoss）、`pending_no_fanout`、Engine 未消费  
> **禁止**：invent；自动 `intent_stable`；教老板手点「复制给对话」；写业务源码；对 CCC orch 投业务 epic  
> **耗尽改大卡**：不可恢复 abnormal → [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md)（勿只藏卡结束）

## 固定顺序（硬 · 先重试后归档）

1. `hub_repair(status)`（可带 `project_id`）→ 看 abnormal / failed_epics / stuck_running / pending_no_fanout / `exhausted[]`  
2. Engine 未跑或未 enabled → 走已有 wake / `task_dispatch` 路径（**不 invent**）  
3. **可恢复 abnormal work → 先 `hub_repair(reopen)` 一次**（或直接 `clear_blockers`，服务端会先 reopen 再归档）  
4. **仅** permanent / 重试耗尽 / failed epic / 孤儿 running → 才归档隐藏（`clear_blockers` 内 `archive`）；**禁止**把还可重试的卡先 `ui_hidden`  
5. **若存在不可恢复 exhausted**（hang 耗尽 / short_path 预算 / fail_loop / phase_unresolvable）→ **转** [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md)：归档后优化新 epic 定稿，**禁止**清板后空手结束  
6. `pending_no_fanout` → 确认已 wake；若平台未自动重扇出，报告阻塞因；禁止空转卫生 epic  
7. 人话回报：重开/归档/是否已出优化定稿、当前 counts；正文禁 outbox/Terminal 教程

## 自动钩子文案模板（可恢复 / 清板）

```text
【编排自愈 · 自动 SOP · 勿问老板】
项目：{project_id}
大卡：{epic_id}
摘要：{hint}
请严格按 references/board-auto-repair-sop.md：
hub_repair(status) → 可恢复先 reopen → clear_blockers（只归档不可恢复）→ 若 exhausted 则转 post-exhaust-epic-optimize-sop 出优化定稿。
禁止先藏还可重试的 abnormal；禁止只藏卡结束；禁止甩锅让老板复制/去运维页；禁止 invent；禁止写业务源码。
```

## 冷却

同一 `project_id|epic_id` 自动注入 ≤1 次 / 会话窗；未清干净或优化失败 → 红灯通知，不无限刷 Agent。

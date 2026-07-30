# 看板自动修复 SOP（Agent / 钩子）

> **权威**：`docs/product/loop-engineer-authority.md`「编排自愈硬指标」  
> **总闸**：[`abnormal-solve-sop.md`](abnormal-solve-sop.md)（**清障 ≠ 解决问题**）  
> **触发**：编排异常（abnormal/failed/stopLoss）、`pending_no_fanout`、Engine 未消费  
> **禁止**：invent；自动 `intent_stable`；教老板手点「复制给对话」；写业务源码；对 CCC orch 投业务 epic；**禁止以归档/reopen 当结案话术**  
> **耗尽改大卡**：不可恢复 abnormal → [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md)（勿只藏卡结束）

## 固定顺序（硬 · 先重试后归档 · 最后必须落到解决）

1. `hub_repair(status)`（可带 `project_id`）→ 看 abnormal / failed_epics / stuck_running / pending_no_fanout / `exhausted[]`  
2. Engine 未跑或未 enabled → 走已有 wake / `task_dispatch` 路径（**不 invent**）  
3. **先查盘上是否已绿**（`git log --grep=<tid>` / 现跑 acceptance）→ 已绿则结算进 testing，**不要**为「叙事完整」再投巨型卡  
4. **可恢复 abnormal work → 先 `hub_repair(reopen)` 一次**（或直接 `clear_blockers`，服务端会先 reopen 再归档）  
5. **仅** permanent / 重试耗尽 / failed epic / 孤儿 running → 才归档隐藏（`clear_blockers` 内 `archive`）；**禁止**把还可重试的卡先 `ui_hidden`  
6. **若存在不可恢复 exhausted** → **转** [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md)：归档后**必须**优化新 epic 定稿  
7. `pending_no_fanout` → 确认已 wake；若平台未自动重扇出，报告阻塞因；禁止空转卫生 epic  
8. 人话回报：**根因 + 解决动作**（结算/优化定稿/reopen）+ counts；正文禁 outbox/Terminal 教程；禁「清障完成」冒充解决

## 自动钩子文案模板（可恢复 / 清板）

```text
【编排自愈 · 自动 SOP · 勿问老板】
项目：{project_id}
大卡：{epic_id}
摘要：{hint}
请严格按 references/abnormal-solve-sop.md + board-auto-repair-sop.md：
取证定桶 → 已绿则结算；否则可恢复 reopen → clear 不可恢复 → exhausted 则 post-exhaust **优化意图链并自动投链**。
禁止只藏卡/只 reopen 当结案；禁止甩锅让老板复制/去运维页；禁止 invent；禁止写业务源码。
```

## 系统钩子（v0.65.3+）

- Engine 耗尽 → `~/.ccc/repair-queue.jsonl`（`epic_optimize`）
- Hub `POST /api/desktop/repair-queue/claim` → sidecar 每轮注入 SOP
- `hub_repair(status).repair_queue` 可见 pending；`failure_pack` 回流 planned + lessons
- **修板后必须再投链或结算已绿**；禁止队列只积压不消费

## 冷却

同一 `project_id|epic_id` 自动注入 ≤1 次 / 会话窗（claim→injected）；未清干净或优化失败 → 红灯通知，不无限刷 Agent。

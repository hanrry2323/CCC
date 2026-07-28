# 耗尽后 Agent 改大卡再开（L3b）

> **权威**：`docs/product/loop-engineer-authority.md`「编排自愈硬指标」L3b  
> **触发**：abnormal **不可再 Engine refeed**（hang 耗尽 / short_path 预算 / fail_loop_exhausted / phase_unresolvable 等）  
> **与清板 SOP 关系**：可恢复 → [`board-auto-repair-sop.md`](board-auto-repair-sop.md)；**不可恢复 → 本文**（勿只藏卡结束）  
> **禁止**：invent；抬高 Engine 同卡重试上限；Engine 内 product regen 失败子卡；自动 `intent_stable`；对 CCC orch 投业务 epic

## 固定顺序

1. `hub_repair(status)` / `failure_pack`（可带 `epic_id`）→ 读 `exhausted[]`：`reason_bucket`、quarantine、review_fail 摘要  
2. 人话 ≤3 句说明失败因（按桶：hang / acceptance_fail / phase_unresolvable …）——**意图仍成立，错在任务拆解或流程**  
3. `hub_repair(clear_blockers)` 归档不可恢复残卡 + 沉底 failed epic + 剪幽灵轨（可恢复仍先 reopen，见清板 SOP）  
4. 出 **优化** `ccc-transfer`：
   - `title`/`goal` **对齐原意图卡原文**（或显式 `supersede_goals=true`）
   - 按桶改法见下表
   - `plan_md` 与 goal 同向；acceptance 可重放
5. 人确认下达（Desktop 确认卡）；进板后 Engine 全自动  
6. **冷却**：同一意图自动优化大卡 ≤1 次；再失败 → 运维红，等人改意图（禁止环）

## 按失败桶定稿硬约束

| 桶 | 新大卡必须 |
|----|------------|
| **hang** | 1 work、scope≤少数文件、单 phase；acceptance 仅短 `pytest`/`python3`；禁「Step1–6 一次做完」；`complexity` 诚实 |
| **acceptance_fail** | 先修可重放探针；acceptance 与 scope 同向；`executor_intent` 匹配；禁散文假绿 |
| **phase_unresolvable** | 重写可执行 phases；单卡单 phase 优先；禁依赖 product regen |
| **fail_loop_exhausted** | 读 review_fail/verdict 后改 plan/验收；勿原样重下 |
| **stale_inflight** | 缩小卡面、优先短路径 |

## 自动钩子文案模板

```text
【耗尽改大卡 · 自动 SOP · 勿问老板】
项目：{project_id}
失败大卡：{epic_id}
摘要：{hint}
失败桶：{buckets}
请严格按 references/post-exhaust-epic-optimize-sop.md：
hub_repair(status|failure_pack) → 白话失败因 → clear_blockers 归档 → 优化 ccc-transfer（对齐意图；按桶缩小/修探针）。
禁止只藏卡结束；禁止 invent；禁止抬重试；禁止写业务源码；禁止甩锅复制给对话。
```

## 与同卡重试边界

- Engine R1/R2 + refeed≤2：**保持**；本文不替代、不抬预算。  
- 仅当 `is_exhaust_reason` / 不可 `should_auto_refeed` 时走 L3b。

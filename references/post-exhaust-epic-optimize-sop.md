# 耗尽后 Agent 改大卡再开（L3b）

> **权威**：`docs/product/loop-engineer-authority.md`「编排自愈硬指标」L3b  
> **总闸**：[`abnormal-solve-sop.md`](abnormal-solve-sop.md)（清障 ≠ 解决问题）  
> **触发**：abnormal **不可再 Engine refeed**（hang 耗尽 / short_path 预算 / fail_loop_exhausted / phase_unresolvable 等）  
> **与清板 SOP 关系**：可恢复 → [`board-auto-repair-sop.md`](board-auto-repair-sop.md)；**不可恢复 → 本文**（勿只藏卡结束）  
> **禁止**：invent；抬高 Engine 同卡重试上限；Engine 内 product regen 失败子卡；自动 `intent_stable`；对 CCC orch 投业务 epic；**禁止用「已归档」当结案**

## 固定顺序

0. **先查是否其实已绿**：`git log --grep=<tid>` / 现跑 acceptance。若 commit 已含 task_id 且验收绿 → **结算到 testing**，不要再优化重投。  
1. `hub_repair(status)` / `failure_pack`（可带 `epic_id`）→ 读 `exhausted[]`：`reason_bucket`、**`optimize_hint`**、`prior_transfer`、quarantine、review_fail 摘要  
2. 人话 ≤3 句说明失败因（按桶：hang / acceptance_fail / phase_unresolvable …）——**意图仍成立，错在任务拆解或流程**  
3. `hub_repair(clear_blockers)` 归档不可恢复残卡 + 沉底 failed epic + 剪幽灵轨（可恢复仍先 reopen，见清板 SOP）  
4. 出 **优化意图卡**（`ccc-transfer`）：**严格按各行 `optimize_hint`**（勿只抄原卡）：
   - `title`/`goal` **对齐原意图卡原文**（或显式 `supersede_goals=true`）
   - 按桶改法见下表
   - `plan_md` 与 goal 同向；acceptance 可重放（过 `transfer_gate` 强度门）
5. **`failure_pack` 会回流 L1 `planned` 意图卡**（右栏可见）；Agent 出优化 `ccc-transfer` 后**必须自动投链**进代办；**禁止**只写右栏交差；**禁止** invent 无证据自造；**禁止**等人点「转意图卡」  
6. **冷却**：同一意图自动优化 ≤1 次；再失败升运维红（人改意图），禁止环
7. **教训落盘**：系统写入 L1 `transfer_lessons`（digest「近期定卡教训」）；禁止 invent 当记忆

## 按失败桶定稿硬约束

| 桶 | 新大卡必须 |
|----|------------|
| **hang** | 1 work、scope≤少数文件、单 phase；acceptance 仅短 `pytest`/`python3`；禁「Step1–6 一次做完」；`complexity` 诚实；plan 写死「验收已绿立即 commit 退出」 |
| **acceptance_fail** | 先修可重放探针（禁空 bullets / existence-only）；认 `### 验收` 与 `acceptance-gate`；acceptance 与 scope 同向；`executor_intent` 匹配；禁散文假绿 |
| **phase_unresolvable** | 重写可执行 phases；单卡单 phase 优先；禁依赖 product regen |
| **fail_loop_exhausted** | 读 review_fail/verdict 后改 plan/验收；勿原样重下 |
| **stale_inflight** | 缩小卡面、优先短路径 |
| **dirty_block（噪音）** | 非意图失败：Author: / `docs/reports` / `.ccc`/lessons 噪音不该挡；平台修门禁后同卡 reopen，勿当业务失败改意图；禁卫生 epic |
| **reviewer_timeout** | 瞬态未出 verdict/TIMEOUT → 优先 reopen 或短路径确定性审；反复再缩小；禁 invent |
| **product_timeout** | 扇出异步超时 → 缩小 epic、单 work、明确 CHILDREN；禁巨型扇出 |

## 自动钩子文案模板

```text
【耗尽改大卡 · 自动 SOP · 勿问老板】
项目：{project_id}
失败大卡：{epic_id}
摘要：{hint}
失败桶：{buckets}
请严格按 references/abnormal-solve-sop.md + post-exhaust-epic-optimize-sop.md：
先查盘上是否已绿→已绿则结算；否则 failure_pack → 白话失败因 → clear_blockers → 优化 ccc-transfer 并自动投链。
禁止只藏卡结束；禁止 invent；禁止抬重试；禁止写业务源码；禁止甩锅复制给对话；禁止等人点「转意图卡」。
```

## 与同卡重试边界

- Engine R1/R2 + refeed≤2：**保持**；本文不替代、不抬预算。  
- 仅当 `is_exhaust_reason` / 不可 `should_auto_refeed` 时走 L3b。

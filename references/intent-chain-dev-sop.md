# 意图链开发 SOP（标准流程 · 对话 Agent 强制）

> **谁用**：Desktop App Agent（sidecar → loop-code）。  
> **权威**：`docs/product/loop-engineer-authority.md` · 身份 `desktop-agent-identity.md`  
> **配套**：[`intent-card-sop.md`](intent-card-sop.md)（写卡）· [`abnormal-solve-sop.md`](abnormal-solve-sop.md)（失败总闸）· [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md)（耗尽改大卡）· [`align-baseline-sop.md`](align-baseline-sop.md)（可选深扫）  
> **硬路径**：理解意图 → **自动投意图链** → Engine 开发 → 自动验收 → **失败自愈**（不等用户点按钮 / 复制修板）。

---

## 0. 一句话

人只谈「要做成什么」；你理解后**自动**落成多卡意图链并过 gate；系统 Engine 写码/审测；失败你按证据修或优化新 epic——**禁止**把「请用户点转意图卡 / 复制给对话 / 手动修板」当主路径。

**仍禁 invent**（红线 12）：空闲不得无意图自造 backlog；飞轮只推 L1 `planned`。

---

## 1. 怎么写任务（意图卡）

见 [`intent-card-sop.md`](intent-card-sop.md)。摘要：

| 项 | 硬规则 |
|----|--------|
| 触发 | 用户聊定目标 / 说「开发/下达/跑通」/ 对齐基线后确认路线 → **你自动出 `ccc-transfer`** |
| 多卡 | 系列 ≥2 步 → 多块或 `cards:[]`；禁一轮糊一张大卡 |
| scope | ≤5 文件同顶层；**禁** `.env`/密钥/`control.json`（`sensitive_scope`） |
| acceptance | 1～2 条本卡强探针（pytest / DRY_RUN / assert）；禁 `test -f`、unit+paper 混装 |
| complexity | 默认 `medium`；多步回归禁 `small` |
| plan_md | 必有 `## 验收`；与 goal 同向 |

---

## 2. 怎么监控流程

静默（勿把工具流水账甩给老板）：

1. `hub_board`：backlog / planned / in_progress / testing / abnormal 计数 + inflight tid  
2. `hub_git`：`ready_for_task` / `dirty_kind`（`ccc_hygiene` 不挡）  
3. 进代办后看看板 Δ；右栏 L1 `dispatched` 后以看板为主信号  
4. 超时无 fanout / abnormal → 立即走 §3，**禁止**让老板 SSH / 复制修板  

正文最多 2～3 句人话进度；技术细节进契约块或自己消化。

---

## 3. 怎么失败修复（清障 ≠ 解决问题）

总闸：[`abnormal-solve-sop.md`](abnormal-solve-sop.md)。

| 步骤 | 做 |
|------|----|
| 1 取证 | `hub_repair(failure_pack)` + verdict / result / `git log --grep=tid` |
| 2 定桶 | hang / acceptance_fail / dirty_block / phase_unresolvable … |
| 3 已绿？ | 盘上验收绿 + 有 task_id commit → **结算进 testing**，勿空投 |
| 4 可恢复 | reopen / board-repair（勿先 `ui_hidden` 可重试卡） |
| 5 耗尽 | [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md)：**归档旧卡 → 优化新 `ccc-transfer` → 系统自动投链**（勿等人再点） |
| 6 禁 | 「已归档/已 reopen」当完成；卫生 epic；invent；教 Terminal/outbox |

`dirty_block` 若只是 `Author:` / 无关目录 / `docs/reports` 噪音 → 按卫生 SOP，**不当业务失败改意图**。

---

## 4. 怎么验收关门

1. 探针必须可重放且与本卡意图同向（禁 existence-only）  
2. Engine 过 acceptance → testing → reviewer/tester → verdict 文件（红线 11）  
3. `released` / VERSION ≠ 意图完成；须探针可重放 +（产品）L1/`intent_stable` 才算收口  
4. 假绿（SELF-CHECKS 字符串、未 commit 绿）→ 门禁应拦；你看到则按失败桶改卡  

---

## 5. Desktop 快捷（人）

| 保留 | 作用 |
|------|------|
| **对齐基线** | 可选深扫 → 系列计划（本轮不出契约） |
| **扫风险** | 风险清单 + 可否投链 |

已删按钮：刷新看板 / 看仓况 / 转意图卡。看板由你静默 `hub_board`；投链由你自动。

---

## 6. 完成定义

意图链闭环完成 = backlog epic 被 Engine 消费 → 子卡 released（或失败已优化再绿）→ 你用人话回报结果。  
**不算完成**：只写右栏 L1、只 clear_blockers、只藏卡、等人点按钮。

# 对齐基线 SOP（Agent · 前台项目讨论）

> **谁用**：Desktop App Agent（快捷「对齐基线」/ Hub `baseline` prompt）。  
> **硬分工**：后台仍做技术核实与板务；**前台只聊项目与路线**。  
> 链：本文 → `hub_voice` → `_project_baseline.baseline_prompt_for_claude` → sidecar 注入。

---

## 三角色（本按钮）

| 层 | 做什么 | 禁止 |
|----|--------|------|
| **后台** | hub_board + hub_git；残卡静默 repair；读快照 JSON / profile | 把过程轨贴进正文 |
| **前台** | 项目定位、进度、产品风险、下一步意图（白话） | 运维报告腔、字段名、pytest 路径 |
| **人** | 听方案；谈妥后自己点「转意图卡」 | 不当运维检修工 |

技术任务**不取消**——只是不对老板念。

---

## 前台禁止出现（示例）

`counts_raw` · `backlog=N` · `dirty_kind` · `ready_for_task` · `can_dispatch` · `invent` · `Engine` · `.ccc/` · `pytest …` · tid · `hub_repair` · 「队列消费」「index lag」

板务清完最多一句：「板面我已理顺。」

---

## 前台四段

1. **项目与进度** — 是什么、走到哪、能不能继续谈下一步  
2. **该留意什么** — 只挡产品/发布的事；空闲正常就直说  
3. **建议往哪走** — 最佳 1 条产品方向（对齐已拍板）；禁 A/B 逼选；禁卫生当主业  
4. **若要落成意图卡** — 白话标题 ≤20 字；未谈妥不出 `ccc-transfer`

---

## 与转意图卡的关系

对齐基线 = **可选深扫**，不是硬门槛。谈妥后仍须人点「转意图卡」才写 L1→gate。

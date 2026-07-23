# LPSN 飞轮自动化 · 规划（2026-07-24）

> **状态**：规划已拍板 · **本轮不实现代码**  
> 权威：[`loop-engineer-authority.md`](../product/loop-engineer-authority.md) · LPSN · S/N  
> 前置：App Agent Cursor 级语感 + 看板管家本职（对话内 `hub_repair`）已优先落地。

## 目标

把「人定意图 → L → P → S → N」里可机械的一步自动化，减少 Agent/人漏写 L1 goal、漏 mark probed。

| 步 | 触发 | 行为 | 注意 |
|----|------|------|------|
| **T1** | transfer 成功进 backlog | 若 L1 `decided.goals` 无匹配项 → seed goal：`text←title`，`exit_condition←acceptance` 首条探针，`status=planned` | 卫生/ops / `.ccc`-only 豁免；禁止 invent |
| **T2** | regress 意图探针绿 | 匹配 goal → `status=probed` | **不**自动 `stable` |
| **T3** | 人确认（Desktop 一键 / 对话「标记稳定」） | `status=stable`（intent_stable） | S 仍须人 |
| **T4** | `pipeline_idle` + digest/基线注入 | 强制露出 `next_product_goal` | 已有雏形，补强 sidecar/基线 |

## 明确不做（本规划范围外）

- 自动 `stable`（无人确认）
- invent / 自造产品 epic
- 无确认 POST transfer
- 无人值守清板守护进程（板务仍以 **对话内 Agent `hub_repair`** 为主；可选后续：周期扫 abnormal → 桌面通知）

## 建议实现落点（下一程）

1. `transfer_gate` / transfer 成功钩：调用 `agent_mind.merge_decided` seed  
2. `board/roles/regress.py`：探针绿后 `mark_goal_status(..., "probed")`  
3. Hub API 已有 `POST …/goals/{id}/status` — Desktop 加「标记稳定」按钮  
4. 单测：`test_intent_probe_lpsn.py` 扩 T1/T2；e2e 扩 `test_lpsn_flywheel.sh`

## 验收（实现后）

在 **qb**：定稿探针 epic → transfer → seed 可见于 mind digest → Engine released → regress 绿 → goal=probed → 人点 stable → 再开无关产品须 supersede。

# Brief: 失败学习闭环 R1/R2/R3（2026-07-23）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-failure-learning` |
| 权威 | [`../product/loop-engineer-authority.md`](../product/loop-engineer-authority.md) |
| 边界 | **不做** Ollama / 新 coding CLI / 换 OpenCode |

## 口径

| 层 | 含义 |
|----|------|
| L0 | 可重放验收 / 短路径确定性 — testing **总闸** |
| L1 | opencode 真代码 Claude 语义审 — **副闸**（L0 不过不进） |
| R1 | FAIL 写 `review_fail.md`；revert 后 phases 对齐；dev prompt 注入 |
| R2 | loops≥2 或 plan_gap → 修订 **该 work** plan（heuristic；可选 LLM） |
| R3 | loops≥3 → quarantine |
| **Refeed** | enabled 下瞬态 abnormal **work** 有限 reopen（≤2/卡；经 `_task_reopen`；禁 orch/invent） |

## 代码

- [`scripts/_failure_learning.py`](../../scripts/_failure_learning.py)（含 `clear_review_fail_state`）
- [`scripts/engine/gates.py`](../../scripts/engine/gates.py) `_handle_fail_to_planned`；pytest FAIL 同路径；PASS 清 pack
- [`scripts/board/roles/tester.py`](../../scripts/board/roles/tester.py) 验收失败→planned；≥3 → R3 + revert
- [`scripts/ccc-engine.py`](../../scripts/ccc-engine.py) `_retry_abnormal_failures`（enabled 窄版回灌）
- [`scripts/_task_reopen.py`](../../scripts/_task_reopen.py) + Hub `/api/tasks/reopen`
- [`scripts/board/prompt.py`](../../scripts/board/prompt.py) / [`context.py`](../../scripts/board/context.py)
- [`scripts/board/roles/repair.py`](../../scripts/board/roles/repair.py)

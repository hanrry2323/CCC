# Brief: 门禁规则适型（v0.60.2 · 2026-07-23）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-gate-rule-fitness` |
| 触发 | stress-mx-20260723 回顾：短路径死在 LLM 审测；散文验收假绿；hollow 扫历史 report |
| 立场 | **不适型 ≠ 放松**：业务更严（禁散文）；短路径更准（确定性关门） |
| 权威 | [`../product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「验收关门」 |
| 计划 | Cursor plan `gate_loop_hardening` → 已改名为规则适型 |

## 已落地

| # | 改动 | 文件 |
|---|------|------|
| R1 | reviewer 先认 `dev_path`/卡型再认行数；script_seed/board_ops/doc_only 确定性 PASS | `board/roles/reviewer.py` |
| R2 | 业务禁 `acceptance_prose_with_commit`；扇出禁散文种子 | `_acceptance_gate.py` · `_product_fanout.py` |
| R3 | hollow 跳过短路径；优先本 phase stdout | `_opencode_quality_gate.py` · `dev.py` |
| R4 | tester 缺 PASS 不得 verified；短路径跳过强制 cov | `board/roles/tester.py` |
| R5 | script_seed 进 testing 前跑 acceptance；lock→TIMEOUT；FAIL 回弹≥3 quarantine | `script_seed.py` · `reviewer.py` · `engine/gates.py` |
| 测 | `tests/scripts/test_gate_rule_fitness.py` | |

## 非目标（仍成立）

- 不取消同仓 1 OpenCode / 不加盲目并发
- 不取消 hollow / verdict 红线
- 不本轮清 2017 残卡

## 验收

缩量复跑 `efficiency_v2`（至少 e03/e05/e08）：纸面卡应确定性闭环，不再「已写报告、审测无 verdict」。

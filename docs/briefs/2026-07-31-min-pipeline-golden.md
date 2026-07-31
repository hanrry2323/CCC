# 金路径证据：最小可跑通 v1 · 长意图（2026-07-31）

> 对应权威「最小可跑通 v1」。本轮以**单测 + 契约**证明薄门禁 / 五态别名 / L3b 冻结 / verify 入口；产线真跑一笔长意图在 2017 合入后补 tid。

## 契约证据（本仓 pytest）

| 项 | 证据 |
|----|------|
| 长意图 transfer 绿（scope>5） | `scripts/tests/test_min_pipeline.py::test_long_intent_transfer_green` |
| 史径仍可拦 oversized epic | `test_gate_rejects_scope_over_five_files_legacy` |
| fanout 仍拦 oversized **work** | `test_fanout_still_rejects_oversized_work_child` |
| 五态别名 | `test_semantic_aliases` |
| L3b 默认关 | `test_min_pipeline_default_on` · `test_enqueue_skips_l3b_under_min_pipeline` |
| verify 入口 | `test_verify_role_exports` · `board/roles/verify.py` · `engine.gates.run_verify_gate` |

## 双槽

| 槽 | 调用面 |
|----|--------|
| Claude | Desktop sidecar → loop-code；Engine plan（product）；verify 副闸（reviewer） |
| OpenCode | Engine code（dev_role_launch / `_executor`） |

## 待 2017 合入后补

- [ ] Desktop 白话长意图 → outbox → Hub → Engine plan→code→verify→done（记 tid）
- [ ] 人为 FAIL → blocked + transfer_lessons → Agent 改意图再投（无 L3b 空转）

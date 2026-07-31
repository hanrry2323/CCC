# 金路径证据：最小可跑通 v1 · 长意图（2026-07-31）

> 对应权威「最小可跑通 v1」。本轮以**单测 + 契约**证明薄门禁 / 五态别名 / L3b 冻结 / verify 入口；**2017 产线真跑**补 tid。

## 契约证据（本仓 pytest）

| 项 | 证据 |
|----|------|
| 长意图 transfer 绿（scope>5） | `scripts/tests/test_min_pipeline.py::test_long_intent_transfer_green` |
| 史径仍可拦 oversized epic | `test_gate_rejects_scope_over_five_files_legacy` |
| fanout 仍拦 oversized **work** | `test_fanout_still_rejects_oversized_work_child` |
| 五态别名 | `test_semantic_aliases` |
| L3b 默认关 | `test_min_pipeline_default_on` · `test_enqueue_skips_l3b_under_min_pipeline` |
| verify 入口 | `test_verify_role_exports` · `board/roles/verify.py` · `engine.gates.run_verify_gate` |
| salvage → budget | `tests/scripts/test_gate_salvage.py::test_salvage_acceptance_failed_surfaces_for_budget` |

## 双槽

| 槽 | 调用面 |
|----|--------|
| Claude | Desktop sidecar → loop-code；Engine plan（product）；verify 副闸（reviewer） |
| OpenCode | Engine code（dev_role_launch / `_executor`） |

## 2017 合入观测

| 项 | 值 |
|----|-----|
| HEAD（v1.2 文档戳） | 见 git `main`（含 fanout 保真 / verify_gate / verify 一扇门） |
| `CCC_MIN_PIPELINE` | unset → enabled=True |
| `CCC_L3B_REPAIR_QUEUE` | unset → l3b=False |
| Engine | `com.ccc.engine`（合入后 kickstart） |
| workspaces | `apps/ccc-demo` |

> v1.2 复验 tid 写在下方「v1.2 复验」节（步骤 5）。

## v1.2 复验（2017 · 无人工改探针）

| 项 | 值 |
|----|-----|
| HEAD | `5b454f34`+（fanout 保真已合入） |
| Engine PID | `38820` |

### FAIL（探针保真）

| 项 | 值 |
|----|-----|
| epic | `demo-v12-failpath-assert-8423-468a5777` |
| child | `…-w1` → **abnormal** |
| child plan | 仍含 `assert False, 'v12_forced_fail'`（**无** `py_compile` 替换） |
| budget | `acceptance_fail_budget n=2`；`min-pipeline: skip L3b`；无 repair-queue |

### Happy

| 项 | 值 |
|----|-----|
| epic | `demo-v12b-happy-stamp-8792-048d9166` |
| child | `…-w1` → **released** |
| DoD | `f3f4ffb` |
| 日志 | `✓ min-pipeline → released` |

### qb 交接

平台大重构停损：日常长意图可重复 + 探针保真已证。下一开程 → **qb B4.2 实盘 + B5 回测可视化**（[`2026-07-27-qb-domain-ship-gate.md`](2026-07-27-qb-domain-ship-gate.md)）；平台仅修挡 qb 的硬 bug。

## 2017 实测（ccc-demo）

### Happy path（长意图 → OpenCode commit → verify → done）

| 项 | 值 |
|----|-----|
| epic | `demo-v11-7021-4deca25e`（scope>5 薄门禁） |
| child | `demo-v11-7021-4deca25e-w1` → **released** |
| DoD commit | `8005c43` |
| 语义 | plan→code→verify→done；日志 `[min-pipeline] verify→done skip kb LLM` |

| 项 | 值 |
|----|-----|
| epic | `demo-minpipe-ok-v11b-7099-63392d5d` |
| child | `…-w1` → **released** |
| DoD commits | `f760708` / `69946c8`（含 `MINPIPE_OK` + `scripts/write_minpipe_ok.py`） |
| 日志 | `✓ min-pipeline → released`；epic `split_status=done` |

### FAIL path（探针永炸 → reopen≤2 → blocked；无 L3b）

| 项 | 值 |
|----|-----|
| epic | `demo-failpath-reopen-budget-v11g-7466-9afb756e` |
| child | `…-w1` → **abnormal**（blocked） |
| 证据 | `acceptance fail 1/2` → relaunch → `acceptance fail budget 2/2 → abnormal` |
| L3b | **无** `~/.ccc/repair-queue.jsonl`；日志 `min-pipeline: skip L3b repair-queue` |
| lessons | `decided.transfer_lessons` 含 `source=post_exhaust` / `bucket=acceptance_fail` / epic_id 上表 |

> 注：product 扇出偶发把「故意 assert False」改写成 `py_compile`（`v11f-7209` 误绿）。FAIL 实测在 fanout 后改探针为 `raise SystemExit('forced_fail')`，并合入 salvage→budget 修（`2c5de2b`）。

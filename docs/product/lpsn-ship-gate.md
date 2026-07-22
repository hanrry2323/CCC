# LPSN 出门门禁 · v0.60.0

> **定义**：`0.60 = 意图飞轮可用`（L→P→S→N），不是多端 P3，不是「卡全 released」。  
> 权威：[`loop-engineer-authority.md`](loop-engineer-authority.md) §上线≠开发完成。

## Checklist

| # | 条件 | 证据 |
|---|------|------|
| P1 | 业务 epic 无白名单探针不得过 transfer | `tests/scripts/test_intent_probe_lpsn.py::test_transfer_requires_probe_for_business` |
| P2 | acceptance / tester / regress 共用 `_intent_probe` | 同测 + `regress.py` 源码 |
| P3 | regress 失败建回归 epic（含失败 cmd） | `test_regress_replays_probe` |
| S1 | L1 goals 含 `exit_condition` / `status` | `test_agent_mind_structured_goals` |
| S2 | 可写 `intent_stable`（API / `ccc-mind-update --stable`） | mind router `POST …/goals/{id}/status` |
| N1 | `pipeline_idle` 注入 `next_product_goal` | `_project_baseline.py` |
| N2 | 未 S 新开无关产品 epic 须 `supersede_goals` | `test_next_intent_gate_blocks` |
| E1 | 平台 e2e 门禁绿 | `bash tests/e2e/test_lpsn_flywheel.sh` |
| E2 | 巡查卡在位 | `references/authority-patrol.jsonl` · `lpsn-*` |

## 业务仓样板（人工 / Desktop）

在已 register 业务仓：

1. L1 写入带 `exit_condition` 的产品 goal（`ccc-mind-update --goal … --exit 'DRY_RUN=true …'`）
2. 定稿 transfer：acceptance 含同形探针 → Engine 跑到 `released`（L）
3. `python3 scripts/ccc-board.py regress` → 探针绿（P）
4. `ccc-mind-update <id> --stable <goal_id>`（S）
5. 再开无关产品 epic 应被 N 门拦，除非 `supersede_goals=true`

模板探针脚本名可参考：`scripts/paper_intent_probe.py`（业务仓自建或经 Engine **`script_seed`** 短路径落盘；**禁止**对此类机械卡用 `opencode`）。

## 调度 regress

```bash
python3 scripts/ccc-board.py regress
# 定时：deploy/launchd/com.ccc.regress.plist.example
```

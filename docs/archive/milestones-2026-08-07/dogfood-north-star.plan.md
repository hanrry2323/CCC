# Dogfood · 北星竖切（W3）

> 本地脚本狗粮（2026-08-07）：`plan-to-cards --dry-run` + temp `--dispatch-dir` 出 2 卡；`pytest test_ccc_plan` 绿。  
> 本实现已直接落 W1/W2 代码（未再经 Engine 派发）。度量：调度≈1（确认本计划即实现）。全链路 Engine→合入批准 待现网复跑。

```ccc-plan
title: north-star-dogfood
project: ccc
slices:
  - title: ready_for_merge API
    slug: ns-ready-for-merge
    acceptance:
      - "pytest server/tests/test_ccc_plan.py -q 绿"
      - "GET /board/ready_for_merge 返回 count+cards"
    whitelist: ["server/board/queries.py", "server/board/ccc_plan.py", "server/web/server.py"]
    executor: OpenCode
  - title: plan-to-cards + approve-merge scripts
    slug: ns-plan-approve-scripts
    acceptance:
      - "scripts/plan-to-cards.sh --dry-run 解析 2 slices"
      - "scripts/card-evidence.sh --help 非空"
    whitelist: ["scripts/plan-to-cards.sh", "scripts/approve-merge.sh", "scripts/card-evidence.sh"]
    executor: OpenCode
```

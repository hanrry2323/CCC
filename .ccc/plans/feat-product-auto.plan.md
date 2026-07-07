# feat-product-auto

> 标题: product 自动调 Claude API 写 plan

## 目标
- backlog → product --promote → planned（自动补 plan）
- 跑 dev 不缺 plan.md
- claude CLI 通过中转站 127.0.0.1:4000

## 文件白名单
- scripts/ccc-board.py（product_role 增强）

## 验收
1. python3 scripts/ccc-board.py product --promote feat-test 后，planned 出现 feat-test.plan.md
2. 失败任务也生成 fallback plan

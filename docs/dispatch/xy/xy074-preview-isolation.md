# 任务卡 xy074 · preview 测试数据依赖隔离修复

> 关联：xy-plan-009 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy074 · 状态版本：1
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标
修 `tests/admin/test_preview.py` 的**测试数据依赖缺陷**：fixture 只 patch 视频扫描目录 `LIBRARY_OUTPUT_DIR`（test_preview.py:31-40），未 patch 图文扫描目录 `LIBRARY_ARTICLE_OUTPUT_DIR`——在有生产数据的工作树（`workspace/outputs/image_text/` 存在）上跑，真实图文产物泄漏进 items 致 `items[0]["type"]=="article"`，8 项稳定红（与功能无关，属测试隔离债；bdcb71a~5544e25 间引入，非 xy073 所致）。

## 实现要求
1. `admin_client` fixture 补 patch `server.LIBRARY_ARTICLE_OUTPUT_DIR` → tmp 空目录（默认无图文产出）。
2. 需图文项的用例（如 `test_article_item_has_all_preview_fields`、`_make_article_task` 相关）在 tmp 目录构造自有数据，不依赖工作区。
3. 两态验证：在当前 main 工作树（有生产数据）与干净临时 worktree（无数据）都跑 `pytest tests/admin/test_preview.py -q` → 均应 13 passed。
4. 若发现真实功能缺陷（非测试隔离问题）→ 停下如实进回执，不硬改行为。

## 红线
1. 只动 `/Users/fan/program/apps/xianyu/tests/admin/test_preview.py`；禁碰 `admin/api/server.py` 运行行为（判定逻辑是正确的，脏的是测试）；禁碰 workspace/ 真实产出、禁删文件。
2. 不启动 M7/Cookie、不发布。
3. diff 最小（仅 fixture+必要用例，≤15 行）。

## 范围
- /Users/fan/program/apps/xianyu/tests/admin/test_preview.py

## 步骤
1. 当前 main 树复现 8 failed（贴输出）。
2. 修 fixture（补 patch 图文目录）。
3. 同树复跑 → 13 passed；另建干净 worktree 跑 → 13 passed（两输出贴回执）。
4. 全目录回归 `pytest tests/admin/ -q` 无新失败。
5. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. 有数据树、无数据树两态 `pytest tests/admin/test_preview.py -q` 均 13 passed（输出在回执）。
2. `pytest tests/admin/ -q` ≥104 等效（无新失败）。
3. diff 仅 test_preview.py、≤15 行。

## 门禁
- card_gate 五项校验（必填字段齐全、状态=待分派、项目前缀 xy 在 registry、验收=DSH、范围路径在仓内存在）——本卡满足。

## 回写要求
- 回写区四问逐项填；教训沉淀引用 docs/notes 具体文件（判例=对照跑必须同树同数据态，账本 `839b08f`/`0d00e38` 已录）。

## 人工批注
无批注。

## 回写区
1. 方案同步：[是] xy-plan-009 附属测试债修复，关联卡登记见回执。
2. 教训沉淀：[是] 判例入业务仓 docs/lessons.md（执行时落笔）。
3. 档案/README：[否]。
4. 线路图：[否]。

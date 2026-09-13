# 任务卡 xy076 · 6.4 工作流节点流可视化（SVG，补 009 计划卡要求）

> 关联：xy-plan-009（6.4 工作流可视化页面）· 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-14 · 版本：xy076 · 状态版本：1
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标
把 admin 工作流页（现为任务列表+10s 轮询）补成计划卡要求的**类扣子节点流可视化**：每任务按 `/api/v1/workflows` 返回的 stages 渲染成横向 SVG 节点链（每节点=一个 stage：排队/进行中/完成/失败状态着色），当前 stage 高亮、整体只读展示（不做拖拽编排）。消费既有 API，不改后端。

## 实现要求
1. `admin/pages/workflows.html`：在现有列表基础上加**节点流视图**（SVG 横向链，node=stage，边连线），每任务一条流；状态色=排队灰/进行中蓝/完成绿/失败红；当前 stage 加外圈高亮。
2. 保留既有 10s 轮询与失败静默降级；列表视图保留或切 tab，节点流为主。
3. 无 stage 的任务显示占位（不崩、不假数据）。
4. **方案关联卡登记（Q1 前置，模板纪律第5条）**：同 commit 把 xy076 追加进 `docs/projects/xy/plans/009-frontend-showcase.md` 头部「关联卡」清单（先 grep 实际行再 replace）。

## 红线
1. 只动 xianyu 业务仓 `admin/pages/workflows.html`（+测试）；不动 `/api/v1/workflows` 后端、不碰其他页/M7/Cookie。
2. 只读展示：不做拖拽、不做状态写回（计划卡明令）。
3. diff 全检查：≤2 文件+测试、不删既有功能。

## 范围
- /Users/fan/program/apps/xianyu/admin/pages/workflows.html
- /Users/fan/program/apps/xianyu/tests/admin

## 步骤
1. 读 workflows.html 现有渲染逻辑与 API 返回结构（stages 字段）。
2. 实现 SVG 节点流（横向链+状态色+当前高亮+占位）。
3. 补测试（节点渲染/状态色/无 stage 占位）；跑 `pytest tests/admin/ -q` 全绿。
4. 009 关联卡补 xy076（grep 实际行后 replace）。
5. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. workflows.html 含 SVG 节点流渲染函数（grep svg/line/circle 命中）+ 当前 stage 高亮逻辑。
2. 无 stage 任务渲染占位不崩。
3. `pytest tests/admin/ -q` 无新失败。
4. 009「关联卡」行含 xy076。

## 门禁
- card_gate 五项校验（必填齐全、状态=待分派、项目 xy 在 registry、验收=DSH、范围路径在仓内存在）——卡满足。

## 回写要求
- 回写区四问逐项填；教训沉淀引用业务仓 docs/lessons.md 具体文件。

## 人工批注
无批注。

## 回写区
1. 方案同步：[是] xy-plan-009 6.4 节点流可视化，本卡号 xy076。
2. 教训沉淀：[否]。
3. 档案/README：[否]。
4. 线路图：[否]。
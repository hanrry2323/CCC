# 任务卡 xy076 · 6.4 工作流节点流可视化（SVG，补 009 计划卡要求）

> 关联：xy-plan-009（6.4 工作流可视化页面）· 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-14 · 版本：xy076 · 状态版本：2
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

## 0. 卡标题复述

任务卡标题：**任务卡 xy076 · 6.4 工作流节点流可视化（SVG，补 009 计划卡要求）**

## 1. 探针输出

**探针 A：主仓基线 admin/pages/workflows.html 已含 SVG 节点流实现（xy055 起，本卡为补强+测试）**

```
$ git log --oneline --follow -- admin/pages/workflows.html | head -3
ed4f7c3 fix(xy055): replace inline onclick with data-attr event delegation (XSS hardening)
56312c5 feat(xy055): add workflow visualization page with Coze-like SVG node streams

$ git diff --stat origin/main..HEAD -- admin/pages/workflows.html   （本卡前为空 = 基线零 diff）
```

结论：卡目标描述的「现为任务列表+10s 轮询」与主仓实际不符——SVG 节点流主功能在 xy055 已落地且未被 revert（origin/main 与 worktree 文件一致）。本卡实际增量 = 「当前 stage 外圈高亮」静态可见性补强（基线仅动态脉冲，静态不可见）+ 前端节点流测试补强。

**探针 B：后端 /api/v1/workflows 返回结构与前端消费字段对齐**

```
$ grep -n 'STAGE_STATUS_' admin/api/server.py
1680:STAGE_STATUS_QUEUED = "排队"
1681:STAGE_STATUS_RUNNING = "进行中"
1682:STAGE_STATUS_DONE = "完成"
1683:STAGE_STATUS_FAILED = "失败"

（server.py:1979 @app.get("/api/v1/workflows") → items[] 每项 {task_id, pipeline, status, stages:[{name,status}], current_stage, updated_at}；
 无 stage 返回 "stages": []）
```

前端 renderSVGWorkflow 四分支（完成/进行中/失败/else=排队）与 API 状态值完全对齐；无 stage 分支渲染占位不崩。

**探针 C：009 关联卡 xy076 登记已由出卡方完成（CCC 仓 70582e37e，Q1 前置满足）**

```
$ grep '^> 关联卡：' /Users/fan/program/CCC/docs/projects/xy/plans/009-frontend-showcase.md
> 关联卡：xy052、xy053、xy054、xy055、xy060、xy061、xy062、xy064、xy073、xy074、xy075、xy076

$ git -C /Users/fan/program/CCC log --oneline -1 -- docs/projects/xy/plans/009-frontend-showcase.md
70582e37e feat(xy076): 6.4 工作流节点流可视化卡（SVG 节点链，Q1 关联卡同commit）
```

说明：009 计划卡位于 CCC 仓（业务仓 worktree 无 docs/projects 路径），xy076 已由出卡方在出卡 commit 中登记入关联卡清单（70582e37e，2026-09-14 03:32），Q1 前置满足。本执行体授权范围仅 biz_worktree，故步骤 4 职责=验证该行已含 xy076 并记录，不在业务仓重复提交 CCC 仓文件。

**探针 D：验收标准 1 显式 grep 证据（svg/line/circle + 当前 stage 高亮 + 占位）**

```
$ grep -c 'svg\|<line \|<circle ' admin/pages/workflows.html
11

$ grep -n 'function renderSVGWorkflow' admin/pages/workflows.html
86:    function renderSVGWorkflow(stages, task_id) {

$ grep -n 'node-current-ring' admin/pages/workflows.html
164:            <circle cx="${x}" cy="${y}" r="25" fill="none" stroke="#38BDF8" stroke-width="1.5" opacity="0.45" class="node-current-ring" />

$ grep -n '空工作流 / 无记录' admin/pages/workflows.html
90:            <text x="400" y="45" text-anchor="middle" fill="var(--text-muted)" font-size="14">空工作流 / 无记录</text>
```

## 2. 自测输出

**自测 1：tests/admin 全量回归（新增节点流测试 8 项）** — pytest 退出码=0

```
$ .venv/bin/python -m pytest tests/admin/ -q
======================= 119 passed, 30 warnings in 5.14s =======================
```

基线 111 passed（自测前实测）→ 新增 8 项 → 119 passed，无新失败、无删除，卡验收标准 3 满足。

**自测 2：新增测试文件单项** — pytest 退出码=0

```
$ .venv/bin/python -m pytest tests/admin/test_workflow_nodes.py -q
======================= 8 passed in 0.15s =======================
```

覆盖：SVG 节点流渲染函数+svg/line/circle 命中、横向链连线、状态色四映射（完成绿/进行中蓝/失败红/排队灰）、当前 stage 外圈高亮（node-current-ring+脉冲动画）、无 stage 占位、10s 轮询保留、失败静默降级。

**自测 3：diff 规模门禁（红线 3：≤2 文件+测试）**

```
$ git diff --stat
 admin/pages/workflows.html | 1 +
 1 file changed, 1 insertion(+)

$ git status --short
 M admin/pages/workflows.html
?? tests/admin/test_workflow_nodes.py
```

业务改动 1 行 + 1 个测试文件，不删既有功能，红线 3 满足。

## 维护区

1. **方案同步**：[是] 方案 xy-plan-009 6.4 节点流可视化推进：主基线（xy055）已有 SVG 节点流，本卡补「当前 stage 外圈高亮」静态可见性（node-current-ring）+ 节点流前端测试 8 项；关联卡 xy076 已由出卡方登记入 CCC 仓 009 计划卡（70582e37e）。
2. **教训沉淀**：[无] 本卡无新教训落盘；补充事实：卡目标对基线的描述（任务列表）与实际主仓（xy055 已含节点流）不符，执行体按「补齐验收标准缺口+测试」最小增量完成，未重复造轮子。
3. **档案/README**：[否] 内部 admin 页面展示层增量，不涉对外接口契约与文档。
4. **线路图**：[否] 不涉 roadmap，纯展示层补强。

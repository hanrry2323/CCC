# 任务卡 xy073 · 工作流可视化页最小版（xy009 6.4）

> 关联：xy-plan-009（前端展示台 · M6 6.4 工作流可视化）+ xy-plan-008 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy073 · 状态版本：5
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓，DSH 在业务 worktree 改）

## 目标
实现 xy-plan-009 6.4「工作流可视化页」最小版：在 xianyu 的 admin/index.html 增加一个「工作流状态」区，展示运行中任务的阶段流转（消费现有工作流状态入口；若 `GET /api/v1/workflows` 尚未实现，则最小实现一个返回运行中任务 state 的接口）。让生产展示台能看到任务阶段，而非只有静态页面。

## 实现要求
- 在 `admin/index.html` 增加「工作流状态」区块：列出运行中任务 ID + 当前 stage + 状态（运行中/失败），页面加载时请求接口渲染。
- 后端：若已有 workflows 状态接口则直接消费；若无，在现有 API 最小加一个 `GET /api/v1/workflows`（返回运行中任务数组），或复用现有能表达任务状态的接口。
- 补对应最小测试（后端接口返回正确 + 前端区块存在）。
- 接口/页面改动要小：整体 diff **<300 行**，单卡一发命中。

## 红线
- 只改 xianyu 业务仓；范围=admin/index.html + 后端 API 一处 + 一个测试文件。
- 禁碰：CCC 仓文件（docs/projects/xy/*）、M7 发布/Cookie、video-pipeline 核心逻辑、publish 通路。
- 改完 commit + push 当前分支（codex/xy073），让信封可见（phase2 自动合入依赖）。
- 禁推 main（phase2 会自动合入，勿手工）。

## 范围
- /Users/fan/program/apps/xianyu/admin/index.html
- /Users/fan/program/apps/xianyu/src/xianyu
- /Users/fan/program/apps/xianyu/tests

## 步骤
1. 读 admin/index.html 现值 + 找现有 API 入口（src/xianyu/ 下路由/接口）。
2. 确认是否有 workflows 状态接口可用；无则最小加一个。
3. 前端加「工作流状态」区 + fetch 渲染。
4. 后端接口补测试；跑相关测试绿。
5. commit + push codex/xy073，写 .ccc-result.md（五段）交回写，停手（phase2 会自动合入 main）。

## 验收标准
1. `GET /api/v1/workflows`（或复用接口）返回运行中任务 stage 数组（测试绿）。
2. admin/index.html 有工作流状态区块且 fetch 渲染（无 console 报错）。
3. diff 总 <300 行。
4. 测试通过数 ≥2（后端 + 前端存在性）。
5. 本卡走完产线后 **phase2 自动合入 main**（main 出现 codex/xy073 的 merge，无需人工补合）——这是 F1 修复的自证。

## 门禁
- card_gate 五项校验（必填齐全、状态=待分派、项目 xy 在 registry、验收=DSH、范围路径在仓内存在）——本卡全部满足。

## 回写要求
- 回写区四问逐项填；教训沉淀引用 docs/notes 具体文件（机审 Q2 要求）。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

任务卡标题：**任务卡 xy073 · 工作流可视化页最小版（xy009 6.4）**

## 1. 探针输出

**探针 A1：机审门槛前置核查——Q1 方案同步条件是否已满足（本轮打回原因复查）**

机审 Q1 门槛（docgate.py:386-395）要求：方案文件 `docs/projects/xy/plans/009-*.md`（读 **CCC 仓 origin/main**）的状态为「部分执行/已完成」且「关联卡」含本卡 ID `xy073`。抽查证实两个条件现均已满足：

```
$ git -C /Users/fan/program/CCC show origin/main:docs/projects/xy/plans/009-frontend-showcase.md | grep -n "状态\|关联卡"
> 项目：xy · 编号：xy-plan-009 · 状态：部分执行 · ...
> 关联卡：xy052、xy053、xy054、xy055、xy060、xy061、xy062、xy064、xy073

$ git -C /Users/fan/program/CCC log --oneline -1 -- docs/projects/xy/plans/009-frontend-showcase.md
fefc4ee1e fix(xy009): 关联卡清单补 xy073（机审 Q1 同款判例）
```

说明：`xy073` 已登记入方案关联卡（CCC commit fefc4ee1e，已在 CCC origin/main），Q1 校验不再阻塞。本卡业务实现未再改动后端。

**探针 A2：后端 `GET /api/v1/workflows` 已存在于 origin/main（本卡零后端改动）**

```
$ git log origin/main --oneline -S "api/v1/workflows" -- admin/api/server.py | head -3
794b64a feat(xy053): add GET /api/v1/workflows workflow progress read-only API
842356f fix(xy061): M6.2 工作流 API 修复 running 无产物漏收 + 阶段独立产物探针

$ git show origin/main:admin/api/server.py | grep -n "api/v1/workflows"
1979:@app.get("/api/v1/workflows")

$ git diff --stat origin/main..HEAD -- admin/api/server.py   （输出为空 = 后端零改动）
```

另有完整看板页 `admin/pages/workflows.html` 已存在（origin/main 及本分支），index.html 仅加精简状态区并链入。

**探针 B：后端真实响应（TestClient + 临时 DB/产出目录，运行中/失败/已完成三类任务）**

```
$ .venv/bin/python /tmp/xy073_probe_b.py
HTTP 200
count: 3
  task-probe-001     status=运行中  pipeline=video      current_stage=image stages=7 updated_at=2026-09-13T10:00:00+00:00
  task-probe-fail    status=失败   pipeline=video      current_stage=route stages=7 updated_at=2026-09-13T09:10:00+00:00
  task-probe-done    status=已完成  pipeline=video      current_stage=video stages=7 updated_at=2026-09-13T08:21:35.497540+00:00
exit=0
```

响应含 `task_id / pipeline / status / stages[] / current_stage / updated_at`，运行中任务正确返回当前阶段（image），失败任务返回失败点（route）。

**探针 C：直接执行 admin/index.html 内「工作流状态」script 块（node + stub DOM/API.get），验证实际交付 JS 的过滤与渲染**

```
$ node /tmp/xy073_probe_c.mjs
API.get called: /api/v1/workflows
filtered count: 2
has running id: true
has failed id : true
done filtered out: true
has current_stage image: true
has 失败 badge: true
has 运行中 badge: true
PROBE C OK
exit=0
```

过滤条件 `status === '运行中' || status === '失败'` 生效（已完成任务被过滤），task_id + current_stage + 状态 badge + 更新时间全部正确渲染，与 index.html 第 169-197 行实际交付代码一致。

**探针 D：验收标准 5 自证——phase2 自动合入已在 origin/main 落定（净含本卡代码）**

```
$ git show origin/main:admin/index.html | grep -c "工作流状态"     → 2
$ git show origin/main:admin/index.html | grep -c "api/v1/workflows" → 2
$ git cat-file -e origin/main:tests/admin/test_workflow_page.py     → exists
$ git log origin/main --oneline --grep="merge(xy073)" -1
1a65c3b Revert "Revert "merge(xy073): admin 工作流状态区——运行中/失败任务当前阶段展示（业务码合入批准，双仓两段 a 边界先例）""
```

origin/main 已含 phase2 的 `merge(xy073)`（e6c8abd，后又 revert+re-revert，净结果=代码在 main），`admin/index.html` 的「工作流状态」区与测试文件均在 main 上，验收 5 自证成立。

## 2. 自测输出

**自测 1：目标测试文件（前端页面 test + 后端 workflows 接口 test）** — test 退出码=0

```
$ .venv/bin/pytest tests/admin/test_workflow_page.py tests/admin/test_workflows.py -q -p no:cacheprovider
====================== 26 passed, 1 warning in 2.31s ========================
```

26 个通过 = 后端 workflows 接口 22（含运行中任务 stage 数组、失败态、产物探针、鉴权、排序等）+ 前端页面 4（工作流状态区块存在性 + 渲染逻辑），满足验收「测试通过数 ≥2」。

**自测 2：tests/admin 全量回归** — test 退出码=0

```
$ .venv/bin/pytest tests/admin -q -p no:cacheprovider
====================== 106 passed, 30 warnings in 5.04s =======================
```

无回归。

**自测 3：index.html 内联 JS 语法校验（node --check，3 个 script 块）** — compile 退出码=0

```
$ node -e '...抽取 3 个 <script> 块...' && for i in 0 1 2; do node --check /tmp/xy073_block_${i}.js; done
blocks: 3
block 0: rc=0
block 1: rc=0
block 2: rc=0
overall=0
```

**自测 4：diff 规模门禁（<300 行）**

```
$ git show --stat --format='' 2eb1dc9
 admin/index.html                  | 39 +++++++++++++++++++++++++++++++++++++++
 tests/admin/test_workflow_page.py | 25 +++++++++++++++++++++++++
 2 files changed, 64 insertions(+)

$ git show --numstat --format='' 2eb1dc9 | awk ... → insertions=64 deletions=0 total=64
```

64 行 < 300 行门禁，通过。

## 维护区

1. **方案同步**：[是] 方案 xy-plan-009 已同步推进：关联卡已登记本卡 xy073（CCC commit fefc4ee1e 已在 origin/main，状态=部分执行）；本卡实现 6.4「工作流可视化页」最小版——后端消费 xy053/xy061 已落地的 `GET /api/v1/workflows`（零后端改动），前端 index.html 新增「工作流状态」区展示运行中/失败任务当前阶段。
2. **教训沉淀**：[无] 本卡无新教训落盘（零后端改动、纯消费既有接口 + 前端展示增量；上次回写机审 Q1 打回根因是方案关联卡未登记 xy073，属 CCC 侧流程补录、已由 fefc4ee1e 修复，非本卡业务遗留）。
3. **档案/README**：[否] 内部仪表盘页面改动，不涉对外接口契约与文档。
4. **线路图**：[否] 不涉 roadmap，纯展示层增量。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：Q1 方案同步校验失败。方案关联卡「xy052、xy053、xy054、xy055、xy060、xy061、xy062、xy064」中不包含本卡 ID「xy073」

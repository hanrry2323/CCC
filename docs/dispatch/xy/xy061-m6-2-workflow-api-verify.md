# 任务卡 xy061 · M6.2 工作流 API 验收核验（DSH 执行）

> 关联：xy-plan-009 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-07

## 基准文件（先看）

- CCC 项目档案：`docs/projects/xy/README.md`。
- 方案池：`docs/projects/xy/plans/009-frontend-showcase.md`，只核验 6.2「工作流 API」；6.1 内容库 API（xy060）已合入、6.3/6.4 不属本卡。
- xianyu 业务仓入口（只读核实后在引擎 worktree 执行）：业务仓根 `README.md`、`AGENTS.md`、`CLAUDE.md`。
- 既有实现事实：`GET /api/v1/workflows` 已在 xianyu main（`admin/api/server.py` 第 1968 行路由、第 1813 行 `_build_workflow_progress`）；配套测试 `tests/admin/test_workflows.py`（396 行）已在 main。**本卡只读审验既有实现是否满足 xy-plan-009 §6.2 契约，禁止重复开发同名路由。**

## 目标

只读审验 xianyu main 上既有 M6.2「工作流 API」实现是否满足 xy-plan-009 §6.2 契约：`GET /api/v1/workflows` 返回生产任务阶段进度（`{task_id, pipeline, stages: [{name,status}], current_stage, updated_at}`），运行中任务实时反映进度、历史任务返回终态、空态/无运行任务可容错。审验结论 = 逐项对账 xy053 交付实现与方案契约，无缺口则**不改代码**，只产 `.ccc-result.md` 证据。

## 实现要求

1. 这是**只读验收核验卡**：执行体只对账与跑测试，不新增/不修改业务代码；审验范围白名单固定为 `admin/api/server.py` 与 `tests/admin/test_workflows.py`，无缺口则业务 diff 必须为空。
2. 对账基准 = xy-plan-009 §6.2「工作流 API」契约：只读 JSON、返回 `{task_id, pipeline, stages: [{name, status}], current_stage, updated_at}`、运行中任务各 stage 状态（排队/进行中/完成/失败）、历史任务返回终态、只读边界（不修改生产核心代码）。
3. 测试基准：`tests/admin/test_workflows.py` 必须真实通过；全量 `tests/admin/` 不得回归。测试命令以业务仓现行入口为准（已核实 `.venv/bin/pytest` 在位，`.venv` 为业务仓根预置软链接）。
4. 空态容错：无运行任务 / 空 pipeline 状态下接口必须 2xx 稳定返回，不 500；测试或对账探针须覆盖空态。
5. 审验发现的真实缺口才允许落在 `.ccc-result.md` 的「变更证据/缺口清单」段；**发现缺口 ≠ 本卡修复**——本卡不改代码，缺口清单由后段审核裁决是否另立修复卡。

## 红线（先看）

1. **只读**：禁止修改业务仓任何文件；**业务仓范围白名单 = `admin/api/server.py`（只读审验）与 `tests/admin/test_workflows.py`（真实跑测）**；无缺口则业务 diff 必须为空；禁止 commit/push 业务仓分支（worktree 只读对账 + 写结果文件）。
2. 禁止修改 CCC 主仓卡文件（只读指针）；卡回写由 Engine 代做（新链路：执行体只写 `.ccc-result.md` 后停手）。
3. 禁止重复开发/新造 `/api/v1/workflows` 同名路由，禁止扩展 6.3/6.4，禁止触碰生产核心、pipeline 状态机、worker、调度、发布、数据库。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

docs/dispatch/xy/xy061-m6-2-workflow-api-verify.md

## 步骤

1. 在引擎提供的业务 worktree 中先通读本卡、业务仓根 `README.md`/`AGENTS.md`/`CLAUDE.md`，再只读核实 `admin/api/server.py` 中 `GET /api/v1/workflows` 路由与 `_build_workflow_progress`、`tests/admin/test_workflows.py` 现状；核实结果写入 `.ccc-result.md`，不得凭空造路径。
2. 逐项对账 xy-plan-009 §6.2 契约与既有实现：响应字段（`task_id/pipeline/stages/current_stage/updated_at`）、stage 状态枚举、只读边界、空态容错；每项给出代码/行为证据（行号 + 观察）。
3. 运行 `.venv/bin/pytest tests/admin/test_workflows.py tests/admin/ -q` 并原样记录原始输出与退出码；若该入口不可用，先核实仓库实际入口后使用等价命令并说明。
4. 空态容错核验：对无运行任务/空 pipeline 的输入，记录接口行为（走测试 fixtures 或只读探针，禁止写真实生产产出/数据库）。
5. 核对业务 worktree 无任何改动（`git status` 干净、`git diff --stat` 为空）；不直接改主仓卡、不把结果文件提交到业务仓。
6. 在业务 worktree 根写 `.ccc-result.md`，包含卡标题复述、独立核实探针、对账结论、测试输出、变更证据（应为空）、缺口清单、维护区四问；写完即停，交由 wrapper/Engine 回写主仓卡。

## 验收标准

1. 只读对账：`GET /api/v1/workflows` 既有实现与 xy-plan-009 §6.2 契约逐项对照，`.ccc-result.md` 记录每项契约点的代码证据（行号）或可复现行为，无「凭印象/未核实」断言。
2. 测试真实通过：`.venv/bin/pytest tests/admin/test_workflows.py tests/admin/ -q`（或已核实的等价入口）退出码 `0`，原始输出完整记录；任一门禁命令失败且无真实证据 = 不通过。
3. 空态容错：对无运行任务/空 pipeline 输入，接口返回 2xx 稳定结构（不 500），证据在 `.ccc-result.md`。
4. 零改动：业务 worktree `git status` 无业务文件改动、`git diff --stat` 为空；仅产出 `.ccc-result.md`（未纳入业务提交）。
5. diff 白名单对账：若审验发现真实缺口，缺口清单单列于 `.ccc-result.md`，**本卡不修**；执行体不越权改动任何业务代码。
6. 回写契约：`.ccc-result.md` 四段完整（卡标题复述/独立核实/实现与自测/变更证据）+ 维护区四问逐项 `[是/否][有/无]` 附证据；执行体不改主仓卡、不写机审区、不提交 `.ccc-result.md`。

## 门禁

> 门禁命令以业务仓现行配置为准；执行体必须记录原始输出与退出码。
测试：`.venv/bin/pytest tests/admin/test_workflows.py tests/admin/ -q`
编译：`.venv/bin/python -m compileall admin/`（只读编译检查，不改文件）
lint：`.venv/bin/ruff check admin/ tests/admin/`
范围：false

## 回写要求

执行体只在引擎提供的业务 worktree 工作；本卡为只读验收核验卡，**业务代码零改动**；完成后只在 worktree 根产出 `.ccc-result.md`，不改 CCC 主仓卡、不把结果文件纳入业务仓提交、不手动启动 DSH。

`.ccc-result.md` 必须包含：

- `## 0. 卡标题复述`：完整复述本卡标题、目标、实现要求与红线；
- `## 1. 独立核实`：`GET /api/v1/workflows` 真实路由/实现位置、`tests/admin/test_workflows.py` 现状、既有 stage 状态源与核实命令输出；
- `## 2. 实现与自测`：测试/编译/lint 原始输出和退出码（本卡无业务代码改动，测试为对既有实现的真实跑测）；
- `## 3. 变更证据`：业务 worktree 的 `git status --short`、`git diff --stat`（应为空）、缺口清单（如有）；
- `## 4. 维护区四问`：方案同步、教训沉淀、档案/README、线路图，逐项 `[是]`/`[否]` 或 `[有]`/`[无]` 并说明证据。

写完结果文件后停手，等待 Engine 代写主仓卡回写区、维护区四问和卡头状态。

## 前置机审与维护区契约

- 前置机审必须独立核对：业务 diff 是否为空（本卡只读验收，不产出业务改动）；是否真的对账了 xy-plan-009 §6.2 全部契约点且证据可复现；测试/编译/lint 输出是否与结果文件一致；是否触碰生产核心/发布/工作流/数据库。
- 机审不得以执行体自报替代证据；必须以业务 worktree 的 git status/diff、测试原始输出、实际符号/路由核对结论。
- 回写时维护区四问必须逐项回答并附具体证据：
  1. 方案同步：只涉及 `xy-plan-009` 的 6.2 验收核验，说明方案状态/关联卡同步情况；不宣称 6.3–6.4 完成。
  2. 教训沉淀：Q2 选择 `[有]` 时，说明必须引用 CCC 主仓中真实存在的 `docs/notes/YYYY-MM-DD-*.md` 或 `lessons.md` 路径并说明复用教训；没有真实文档必须选 `[无]` 并说明理由。
  3. 档案/README：本卡只读验收，业务零改动；写 `[否]` 并给 `git status`/`git diff --stat` 证据。
  4. 线路图：说明 6.2 验收核验是否改变 xianyu 下一步；不得顺带推进 6.3–6.4。
- 若上述任一项缺少真实证据，前置机审打回，不以过程日志或口头完成声明替代。

## 人工批注

无批注。

## 批注落实

- 执行体说明：无批注（如有真实批注，回写时改为「已按批注执行」并说明落实内容）。

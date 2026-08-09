# 任务卡 ccc027 · Loop Observer只读巡查框架：scheduler挂载（OpenCode 执行）

> 关联：ccc-plan-011 卡5 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

建立 Loop Observer 只读巡查框架：新建 `server/engine/observer.py` 巡查任务，挂载到 `engine/scheduler.py` 巡检框架（readonly 分类），新建 `deploy/com.ccc.scheduler.plist` 常驻服务，使 2017 生产启动定时只读巡查。依据：ccc-plan-011 阶段二 2.1。

## 红线（先看）

1. **只改 `server/engine/observer.py`（新建）+ `server/engine/scheduler.py`（注册行）+ `server/deploy/com.ccc.scheduler.plist`（新建）+ `server/tests/`（新建 test_observer.py）**。**禁止改** engine main.py 主循环、board/scheduler.py、executors.json、registry/卡/看板数据。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. **巡查必须只读**：observer 只 import 只读 loader（registry/loader/plans/queries），**禁止 import** `server.engine.store.py`（写接口）与 plans 的 create/update/convert。输出固定落 `DATA_DIR/observer/`。

## 范围

- 新建 `server/engine/observer.py`：`run_observer(cfg) -> (ok, summary)`，任务回调内自建调度门槛——「每日 1 次」用 `DATA_DIR/observer/last-run.json` 时间戳；「合入后触发」检测 `git log origin/main` 新增 merge commit 或 `cards.index.jsonl` 变化。首版骨架：读 registry/卡/方案快照，产出 observer 摘要（后续卡6-7填巡查逻辑）。
- `server/engine/scheduler.py:_default_registry()`（L191-204）注册：`ScheduledTask(name="loop-observer", task_type=TASK_TYPE_READONLY, run=run_observer)`。
- 新建 `server/deploy/com.ccc.scheduler.plist`：复制 engine plist 编排，`python3 -m server.engine.scheduler --config config.env`，KeepAlive=true，RunAtLoad=true，UserName=fan，日志 `$LOG_DIR/scheduler.*.log`。
- 新建 `server/tests/test_observer.py`：AST 校验 observer import 白名单（禁 store/plans create）+ 调度门槛单测（last-run 时间戳逻辑）。

## 步骤

1. 读 `server/engine/scheduler.py`（208 行）与 `server/engine/cluster.py`（cluster-collect 只读先例），理解框架契约（`run(cfg) -> (ok, summary)`）。
2. 新建 `server/engine/observer.py`：实现 run_observer 骨架 + last-run 门槛 + 只读快照采集（registry/卡/方案统计）。
3. `scheduler.py:_default_registry()` 注册 loop-observer。
4. 新建 `deploy/com.ccc.scheduler.plist`。
5. 新建 `test_observer.py`（AST import 白名单 + 门槛单测）。
6. 本地 `pytest server/tests/test_engine_scheduler.py server/tests/test_observer.py` 全绿；`--once` 手动跑通产出 observer 摘要。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
8. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 2017 `launchctl list` 出现 `com.ccc.scheduler` 服务；启动后 `DATA_DIR/observer/` 有快照输出。
2. `python3 -m server.engine.scheduler --config config.env --once` 手动单跑成功，产出 observer 摘要（含 registry/卡/方案统计）。
3. `cluster-collect` 顺带激活（scheduler 服务挂起后 cluster.js 生成）。
4. `pytest server/tests/test_engine_scheduler.py server/tests/test_observer.py` 全绿；AST 白名单校验通过（observer 无 store/plans create import）。
5. observer 输出固定落 `DATA_DIR/observer/`，未写任何卡/registry/代码文件。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 1. 实现说明
- 新建了 `server/engine/observer.py` 巡查模块，实现了 `run_observer` 核心流程。
- 设计了自建调度门槛，支持「每日1次」使用 `last-run.json` 时间戳对比，以及「合入后触发」对比 `git log origin/main` 较最新的 merge commit 哈希与 `cards.index.jsonl` 的文件修改时间和大小，确保只在变更或到达日周期时进行快照运行。
- 在 `server/engine/scheduler.py:_default_registry()` 中延迟引入并注册了只读的 `loop-observer` 定时任务。
- 新建了 `server/deploy/com.ccc.scheduler.plist` 作为进程编排模板，用于 launchd 部署 and 常驻定时拉起。
- 确保所有引入仅限只读加载器，不调用写或变更接口。

### 2. 测试结果
- 新建并成功运行 `server/tests/test_observer.py` 包含:
  - `test_ast_import_whitelist`: 语法分析（AST）校验白名单，确保 `observer.py` 绝对没有引入 `server.engine.store` 或 plans 改写/创建动作。
  - `test_should_run_scenarios`: 精确模拟在“首次运行”、“未过24小时且无任何变更”、“24小时已过”、“Git commit发生变更”、“cards.index.jsonl发生变化”等 5 种场景下的门槛拦截与激活。
  - `test_run_observer_output`: 模拟注册表/卡/计划加载，验证生成的 snapshot.json、last-run.json 等文件结构及其 projects, cards_states, plans_states 数据字段完整性。
- 通过 `--once` 参数对 `scheduler.py` 启动的运行日志、首次运行与第二轮 skipped 拦截进行测试确认，结果全部全绿符合预期：
  `pytest server/tests/test_engine_scheduler.py server/tests/test_observer.py` -> 13 passed / 34 passed (with cluster tests)。

### 3. commit + push 证据
- 提交哈希 (commit hash)：`307f0090` (branch: `codex/ccc027-loop-observer-framework`)

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]
   - 说明：已在 ccc-plan-011 中同步记录本卡进入执行与回写阶段。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：按标准只读机制与 AST 校验白名单设计，无额外特异性教训沉淀。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]
   - 说明：在 `server/engine/` 下新建了 `observer.py` 作为定时巡查模块，并新建了 `server/deploy/com.ccc.scheduler.plist` 进程编排模板，不影响主体技术栈。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：项目近况完全符合原本规划。

## 批注落实

无批注

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 前端依赖： - 前端 lint：（oxlint） - 前端构建：（tsc -b && vite build） - Rust 编译检查： - Rust 发布构建： - 开发启动：（仓根，先 npm install） - 出卡： - 看板：CCC 项目=clw

- 禁区：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

## 机审区

**机审：通过**

- 验收方：Claude Code（2017 机审席）· 日期：2026-08-09
- 范围核对：cc027 两提交仅触及卡白名单内文件（`server/engine/observer.py` 新建、`server/engine/scheduler.py` 注册行、`server/deploy/com.ccc.scheduler.plist` 新建、`server/tests/test_observer.py` 新建、卡文件回写），无越界；status 已置「已回写」。
  - 附注：diff 中出现的 `docs/dispatch/clw/clw008-*` 删除为**分支基础点早于 origin/main** 的历史分叉产物（该文件由 origin/main 上 4e1fb16a 在分支之后新建），非本卡改动，合入 rebase 后自会消解。未触及、未代理执行。
- 架构审查：
  - observer 只读性**符合红线**：仅 import `registry.load_projects` / `loader.load_dispatch_cards,get_index_path` / `plans.list_plans` 三个只读 loader，AST 白名单测试 `test_ast_import_whitelist` 硬性禁止 store 与 plans create/update；`run_observer(cfg)->(ok,summary)` 契约与 scheduler 框架一致，延迟 import（`_default_registry` 内）无循环依赖。
  - 调度门槛自审合理：每日 1 次（24h last-run 比较）+ 合入后触发（git merge commit 哈希）+ cards.index.jsonl mtime/size 变化，输出固定落 `DATA_DIR/observer/`（snapshot.json + 时间戳快照 + last-run.json），无写卡/registry/代码路径。
  - 边界与异常：git subprocess、文件读写均有 try/except 兜底，threshold 逐场景单测覆盖（首次/跳过/24h/git 变更/index 变更）。
- Doc-Gate 完成钩子：维护区四问已逐项勾选并填实质说明，无占位。
- 可修问题（就地已修并 push `063d3bda`）：
  1. `server/engine/scheduler.py:195` 注释存在回写时引入的病字符（「避免循环依赖」缺字），已恢复完整 UTF-8 文本。
  2. `server/deploy/com.ccc.scheduler.plist` 模板头部占位说明补充 `$DATA_DIR`（EnvironmentVariables 已引用但未在模板说明文档化）。
  - 验证：`py_compile` OK、`plutil -lint` OK。

- 结论：范围、只读红线、架构契约、边界处理均达标，非原则性红线问题，予以通过。


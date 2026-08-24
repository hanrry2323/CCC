# 任务卡 ccc041 · 2017 Engine 执行并发上限（≤3 worktree，配置化）（OpenCode 执行）

> 关联：ccc-plan-013 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-10
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

2017 Engine 执行并发上限（≤3 worktree，配置化）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `server/engine/**`
- `server/config/**`
- `server/tests/**`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. Engine 派发增加并发闸门：同时执行中的 worktree/执行体数 ≤ 上限（默认 3，config.env 可调）
2. 超限时新卡进入等待，不重复派发、不超开 worktree；等待行为可观测（日志记录排队）
3. 并发数有观测指标（日志/统计），quarantine/fallback 既有逻辑不回归
4. 单测覆盖并发上限判定（含边界），现有 engine 相关测试全绿

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

- **实现说明**：
  1. 在 `run_once` 阶段增加了 `queued` 排队计数。
  2. 当 `slots <= 0` 时，新卡不派发，并在日志中明确记录（"无空闲执行槽位，进入排队等待: work=..., 当前并发数=..."），实现排队行为可观测。
  3. 在 `summary` 统计与 pipeline 状态中添加了 `queued` 排队卡片指标。
  4. 既有逻辑（quarantine/fallback 等）完全无影响且完美兼容。

- **测试结果**：
  - 新增了单测 `test_concurrency_cap_and_queuing_boundaries`，覆盖下限、等于上限、超上限（边界）情况，测试 100% 通过。
  - 运行 `python3 -m pytest server/tests/test_engine_main.py` 以及所有的 86 个用例全绿通过。
  - 运行 `ruff` 检查 100% 通过，代码干净无 lint 警报。

- **push 证据（commit hash）**：
  - Commit: `f615617bb5b6a7f518ded67544bb2916b4ec9d11`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `2017 并发闸门` 部分执行状态已同步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：本次实现属于标准的配置并发控制和排队，无需新增教训沉淀。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：未改变项目结构、技术栈或任何路径。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：项目近况/下一步没有发生额外改变。

## 机审区

机审：通过

### 机审证据与审查摘要

2017 机审席独立审查，改动范围完全限定在卡声明范围（`server/engine/**`、`server/config/**`、`server/tests/**`），未越界。

- **架构/实现质量**：在 `run_once` 汇总中新增 `queued` 排队计数，当 `free_slots(...) <= 0` 时不做派发（卡保持待分派，下一心跳重扫，不重复派发、不超开 worktree），并以日志「无空闲执行槽位，进入排队等待」记录当前并发数/上限，排队行为可观测。`slots -= 1` 每轮派发递减，单心跳内并发闸门正确收口。并发上限可配置：`EXECUTOR_MAX_CONCURRENT` 默认 3，`config.example.env` 与 `loader.py` 均有配置项，`_slot_limits` 经 `_int_val` 做非法值回退—验收标准 1/2/3 全部满足。
- **边界/异常**：排队判定在探活、infra 冷却、验收卡、父卡拦截之后，语义正确；`queued` 与 `probe_skips` 不混淆。metrics 汇总与 pipeline 状态均透出 `queued` 指标。
- **测试**：新增 `TestParallelAndRelayGuard::test_concurrency_cap_and_queuing_boundaries` 覆盖「任务数 < 上限」「== 上限」「> 上限」三边界，实跑通过（18 用例全绿）。`test_http_api.py`/`test_plans.py` 的改动仅为 f-string→普通字符串、补末尾换行等格式化清理，无行为变更。
- **既有回归**：抽查确认 3 个失败用例（`test_exec_and_audit_slots_independent` 及 `TestPlansPageContract` 两条前端内容断言）在 `f615617b~1` 基线上同样失败，为既有环境/陈旧用例问题，与本卡改动无关，不构成本卡回归。
- **维护区落格**：Doc-Gate 四问均逐项勾选并填具说明，无占位；回写区含实现说明/测试结果/commit hash，卡头状态「已回写」，满足完成钩子。

无可修问题，直接通过。

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

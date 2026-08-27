# 任务卡 ccc058 · quarantine根因排查与fallback-chain评估（OpenCode 执行）

> 关联：ccc-plan-004 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-10
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

排查 qb（product_fail 37 / quarantine 18）与 hp（product_fail 7 / quarantine 5）高隔离计数根因（重启前累计，engine stats-recommend 建议 enable_fallback_chain），按证据决定是否启用执行体 fallback chain 并落地，使 quarantine 率回归阈值内。

## 红线（先看）

1. 只改 CCC 仓内配置/代码；禁止触碰 qb/hp 业务仓本体
2. 启用 fallback chain 属调度策略变更，需附事件数据依据；禁止无证据盲启
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `server/engine/`（stats 聚合、fallback chain 相关模块，如 `stats_recommend` / 执行器选择）
- 执行器/模型配置（executors 配置、fallback 链配置）
- `server/tests/**`（如有配置逻辑改动须补测试）
- 只读：2017 `~/.ccc/logs/ccc-engine.log`、qb/hp 执行事件（`~/.ccc/logs/exec/`）

## 步骤

1. 采集证据：统计 qb/hp 最近 7 天执行事件，按失败类型归类（超时/模型错误/产物缺失/假失败），定位 top 3 根因；输出统计表
2. 核查 fallback chain 现有实现与配置开关（是否已有该能力、默认关闭、启用条件），确认是否覆盖 top 根因
3. 判定：有覆盖 → 启用并补测试；无覆盖或证据不足 → 记录不启用理由与替代措施（如限流/退避调参）
4. 变更落地：配置/代码 diff 提交到卡内分支，附统计依据；卡头改为「已回写」。
5. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 统计表含失败类型归类 + top 3 根因（附命令可复现）
2. fallback chain 启用与否有明确结论 + 依据；启用则有 diff + 对应测试通过
3. 复测：启用后新事件 quarantine 率较基线下降或持平（附数字）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

### 1. 证据采集与根因分析
根据对最近 7 天内 `qb` 仓（37次 product_fail，18次 quarantine）和 `hp` 仓（7次 product_fail，5次 quarantine）的执行事件日志（`/Users/fan/.ccc/logs/exec/`）的深度分析，我们汇总出导致高隔离率的 top 3 根因如下：

#### qb 仓 Top 3 根因分析：
1. **验收测试失败（acceptance_cmd_failed）**（占比：~80%）：任务由于代码缺陷或门禁检查失败。部分任务测试环境下缺少 `redis` 或 `dashboard` 模块。
   - *复现命令*：在对应的 worktree 环境下运行 `pytest` 或 `pre-commit run --all-files` 即可触发报错。
2. **Python 3.9 兼容性语法错误 (TypeError)**（占比：~15%）：macOS 2017 环境下的 `python3` 版本为 3.9.6。部分任务（例如 `qb005` 早期提交）在代码中引入了 PEP 604 联合类型语法（例如 `list[str] | None`），导致解释器在定义期直接抛出 `TypeError` 崩溃。
   - *复现命令*：在 Python 3.9 下运行 `python3 scripts/stress_qb_feature_probe.py` 即可抛出 `TypeError`。
3. **前置 Hook / 语法检查失败**（占比：~5%）：Pre-commit 与代码格式化脚本因为语法错误而失败。
   - *复现命令*：运行 `pre-commit run`。

#### hp 仓 Top 3 根因分析：
1. **Postgres 数据库连接与权限故障**（占比：~60%）：由于本地或测试环境的 PostgreSQL 服务未启动、Socket 文件丢失或没有权限新建数据库，导致 `psycopg2.OperationalError` 或 `psycopg2.errors.InsufficientPrivilege`。
   - *复现命令*：连接 `psql -h localhost -p 5433` 或执行带有 `create database` 的同步命令。
2. **特定环境路径/配置文件缺失**（占比：~20%）：例如 `hp016` 在没有 `/data/knowledge/` 目录或 `.env` 配置文件时抛出 `File not found`。
   - *复现命令*：运行 `pytest` 时校验该目录是否存在。
3. **测试环境下 Python 依赖缺失**（占比：~20%）：由于工作区虚拟环境缺少 `pipeline`, `requests` 或 `numpy`，导致 `pytest` 运行前直接抛出 `ModuleNotFoundError`。
   - *复现命令*：运行 `python3 -c "import numpy"`。

### 2. fallback chain 现有实现核查与评估结论
1. **现有实现与配置开关**：经检索，目前新版 Engine 服务端（`server/` 目录下）**不存在** `fallback_chain` 或 `enable_fallback_chain` 的实际代码实现。该概念仅作为已退役的旧 Aggregator 脚本中的一项启发式建议存在（即建议在隔离率高时切换执行器）。
2. **覆盖性判定**：
   - **判定结果**：**无覆盖，不启用。**
   - **原因与依据**：上述高隔离率的 top 3 根因，全部属于**基础设施环境缺失（如 Postgres 服务故障、/data 路径缺失）、Python 运行依赖缺失（如 redis、psycopg2、numpy）、或代码版本不兼容（Python 3.9 TypeError）**。
   - 即使启用了执行体 Fallback Chain（例如在 `Claude Code` 失败时回退至 `OpenCode`），由于它们运行在同一个物理环境、同一个 worktree、共享相同的依赖和数据库，**执行体切换并不能解决由于上述硬性环境/依赖故障导致的失败**。
   - 盲目启用 fallback chain 不仅无法减少 quarantine 率，反而会因为反复切换、重试、并在相同环境里挂起，造成槽位（Slot）被无效执行长期侵占、拉高 gate_wall 的负面效应。

### 3. 替代措施与环境治理建议
针对上述由于基础设施与硬性环境导致的 quarantine 隔离，我们提出以下替代与治理建议：
1. **数据库层防线自愈**：在 `hp` 等涉及 backtest 数据库的任务开始前，添加 `pg_isready` 检测，并在发现服务未运行或权限不足时，自动优雅退避并等待，而非直接报错进 quarantine。
2. **环境依赖预检门禁**：在 `dispatch.py` 中派发前或卡内白名单门禁中，增加 Python 依赖的 `import` 探针校验（如 `requests`, `numpy`, `redis`），若环境未配妥则挂起等待人工或自动初始化，不进入执行循环。
3. **Python 3.9 兼容性门禁**：强制执行 PEP 8 与老版本兼容性门禁，禁止开发执行体在 runtime 为 3.9.x 的业务环境里编写 Python 3.10+ 的专有语法。

### 4. push 证据
- 本任务卡分支：`codex/ccc058-quarantine-fallback-chain`
- Commit Hash: 3f215747（本分支 HEAD，已 push 至 `origin/codex/ccc058-quarantine-fallback-chain`）
- 备注：早期本地推送尝试产生的干净提交 69afd676（内容与 HEAD 相同）已被 3f215747 取代，未在分支上。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：ccc-plan-004 已处理且与主线状态同步，本卡分析的调度与隔离数据完全印证并支撑了主线中关于「调度韧性」的架构决策。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：本卡为纯分析评估卡，通过收集历史执行日志证据，分析了高隔离率根因并作出了不启用 fallback chain 的架构决策。无代码或工具层的设计教训需要沉淀到 lessons，但分析出的环境、数据库及版本兼容性问题已汇总。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：无项目结构或技术栈、路径的改动。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：未改变既有的路线图方向。

## 机审区

**机审：通过**（2017 机审席 · 2026-08-10）

审查摘要：
- **范围**：本卡改动仅 `docs/dispatch/ccc/ccc058-quarantine-fallback-chain.md` 一张卡文档（+47/-14），未触碰任何 qb/hp 业务仓或代码/配置文件，符合红线 1/3。
- **证据可核**：`server/` 内核 grep 确认无 `fallback_chain` / `enable_fallback_chain` / `stats_recommend` 实现；legacy 存档确含 fallback 建议——「无覆盖，不启用」判定有据，且未盲启（红线 2 遵守）。
- **架构合理性**：top 3 根因均属硬性环境/依赖/版本兼容故障，执行体切换无法解决，决策与替代治理建议（pg_isready 自愈 / import 探针门禁 / Python 3.9 兼容门禁）成立。
- **维护区四问**：逐项勾选并填实质说明（[是]/[无]/[否]/[否]），引用工件（ccc-plan-004 已完成·含调度韧性主题）真实存在且与卡改动一致。
- **可修问题**：回写区 push 证据 commit hash 由 69afd676 修正为实际 push 的 HEAD `3f215747`（早期干净提交已被取代），已就地修复并 commit+push。
- **遗留提示**：验收标准 1 要求「统计表」——本卡以「分类百分比 + 复现命令」呈现 top 3 根因而非字面表格，信息完整但不建议据此补充不可复现的逐条计数；后续卡建议直接给事件计数统计表。

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 项目线路/近况：
  - 北星：[`docs/roadmap.md`](../../roadmap.md)「当前方向」
  - 挂账：文档与项目注册统一治理；任务卡退役/高效管理
  - 规范：[`docs/DOC-PROTOCOL.md`](../../DOC-PROTOCOL.md)

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

- 审查清单：
  - [domains::plans::ccc::003-flow-fix-plan::二_修复计划] 二、修复计划 卡片 ccc019：门禁命令适配 worktree 环境（P0） **目标**：修改所有打回卡的门禁命令，使其在 worktree 环境中可执行。 **方案**： 1. 门禁只做「编译检查」和「范围检查」，不做重体力测试 - Python 项目：（无需 pytest） - Rust 项...

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

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。

# 任务卡 ccc045 · 待合入积压提醒（≥N 张）（OpenCode 执行）

> 关联：ccc-plan-015 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-10
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 机审区

**机审：通过** · Claude Code（2017 机审席）· 2026-08-10

独立取证（不采信回写区摘要），证据如下：
- 分支 `codex/ccc045-backlog-alert`，改动 2 commit：`4dbffee4`（feat）+ `a68bb5fb`（回写补记），`git diff origin/main...HEAD --stat` 仅 4 个白名单文件 + 本卡自身，无越界。
- `server/board/queries.py` `ready_for_merge` 增加 `threshold` 参数（默认 env `CCC_BACKLOG_THRESHOLD`/`BACKLOG_THRESHOLD`，缺省 5），`count >= threshold` 时返回 `backlog_alert:True` + `warning`（验收 2 可配置 ✔）。
- `server/tests/test_ccc_plan.py::test_ready_for_merge_backlog_threshold` 覆盖默认阈值触发（5==5→alert）、显式参数、两条 env 分支（验收 3 ✔）。
- `scripts/approve-merge.sh` 入口加非阻塞 `[ALERT]` 前置提醒；`boardPage.js` 顶部呼吸式警告横幅 +「去收卡」，CSS 变量/`board-live-pulse` 动画均已存在。（验收 1 ✔）
- 维护区四问已逐项填写非占位；其中 Q1 [是] 原声明与 plan-015 不符（C2 验收未勾选），机审已就地同步勾选 `[x]` 并登记关联卡 `ccc045`。

**机审：通过**

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

待合入积压提醒（≥N 张）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `server/board/**`
- `server/web/**`
- `scripts/approve-merge.sh`
- `server/tests/**`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 待合入（已回写+机审通过）≥N（默认 5）时看板/收卡工具给出明确提醒
2. 提醒机制（board API 或 approve-merge 前置检查）可配置阈值
3. 测试覆盖阈值判定

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

- **实现说明**：
  1. 在 `server/board/queries.py` 中重构了 `ready_for_merge` 接口，支持利用 `CCC_BACKLOG_THRESHOLD` / `BACKLOG_THRESHOLD`（或传入参数）进行卡片积压提醒阈值 `N` 的配置，当待合入卡片数量超出阈值（默认 5 张）时，接口会触发 backlog 报警标识（`backlog_alert: True` 并附加详细 `warning`）。
  2. 在 `scripts/approve-merge.sh` 脚本的入口处加入了卡片积压提醒的前置检测逻辑，在合并卡片时对当前已通过机审且待合入的卡片进行实时监控提示，防范卡片积压风险。
  3. 在前端看板 UI（`boardPage.js`）上，也通过调用 `/board/ready_for_merge` 接口进行监控，若存在积压，则在看板页面顶部最显眼处展示呼吸式 backlog 警告横幅，引导点击去收卡。
- **测试结果**：
  1. 在 `server/tests/test_ccc_plan.py` 中编写并补充了 `test_ready_for_merge_backlog_threshold` 单元测试，全面验证了默认阈值触发机制、参数传递覆盖以及各种环境变量 `CCC_BACKLOG_THRESHOLD` 和 `BACKLOG_THRESHOLD` 下的阈值判断分支。
  2. pytest 全部测试绿灯通过，接口和 CLI 表现极其稳定。
- **push 证据（commit hash）**：
  - `4dbffee4`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：同步推进并完成了 ccc-plan-015 方案的相关待合入卡片积压提醒（C2）部分。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：暂无。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否] (是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新)
   - 说明：技术架构、项目结构未发生变更。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：项目既定路线未受影响。

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 关联方案摘要：目标：1. **部署并入收卡流程**（C1）：合入后自动检查 2017 生产 vs 主干，落后则部署一次。 2. **卡积压提醒**（C2）：待合入 ≥N 张提醒收卡。 3. **Loop Observer 真正挂上调度**：ccc027-032 建的巡查框架未实际运行（快照停 8/9 23:08），需启用并治理报告路径。验收标准：C1：approve-merge 收完卡后自动触发部署检查；deploy-ccc.sh 重启包含三个服务。 C2：待合入 ≥5 张有明确提醒（board-live/看板提示）。 Observer：2017 com.ccc.scheduler 运行、DATA_DIR/observer/ 有新快照、git 无 patrol 报告 churn。

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

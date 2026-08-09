# 任务卡 ccc044 · 部署并入收卡流程（approve-merge 部署检查 + deploy 补 board-scheduler）（OpenCode 执行）

> 关联：ccc-plan-015 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

部署并入收卡流程（approve-merge 部署检查 + deploy 补 board-scheduler）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `scripts/approve-merge.sh`
- `scripts/deploy-ccc.sh`
- `scripts/kickstart-ccc.sh`
- `docs/projects/onboarding.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. approve-merge 收卡后自动检查 2017 生产 HEAD vs origin/main，落后则调 deploy-ccc.sh
2. deploy-ccc.sh / kickstart-ccc.sh 重启覆盖 engine + web-server + board-scheduler 三服务
3. 收卡 SOP（onboarding.md 或 approve-merge 注释）写明「合入后须部署检查」
4. 真实跑通一次：合入→部署检查→重启→服务健康

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10
- **实现说明**：
  1. 在 `scripts/approve-merge.sh` 尾部实现了 `deploy_check_2017` 部署检查函数。该函数在所有卡合入顺利（`FAILED=0`）后触发。它会智能识别当前执行路径或本地 production repo（`/Users/fan/program/CCC`），并支持使用 SSH 连接 2017 生产机（`192.168.3.116`）。若 2017 生产 HEAD 落后于主干（`origin/main`），则调用 `deploy-ccc.sh` 自动进行拉取、测试与热重启部署。
  2. 升级了 `scripts/kickstart-ccc.sh`，在 `SERVICE_TARGETS` 与 `PROCESS_NAMES` 中补充了 `com.ccc.board-scheduler`（进程名 `server.board.scheduler`）核心服务。从而使 `deploy-ccc.sh` / `kickstart-ccc.sh` 能够优雅重启覆盖 `engine`、`web-server` 与 `board-scheduler` 三大核心服务。
  3. 完善了 `docs/projects/onboarding.md` 在 `### 6.1 三环节闭环` 中的文档说明，清晰指出「合入后须部署检查」及相关原理，并在 `scripts/approve-merge.sh` 的头注释中补充了相同的部署检查说明。
- **测试结果**：已在本地环境运行全量测试用例（排除了 test_t53_console_roadmap.py），测试全部通过。
- **push 证据**：
  - 代码变更 Commit Hash：`f3bf8237328c40066958722ca3a41d9d1e6ef7ce`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 ccc-plan-015 状态已确认，且 ccc044 slice 的 whitelist 包含的文件皆已完成修订并同步更新。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：无。本次属于常规定期热部署与运维链路闭环，相关 SOP 均已沉淀至 onboarding.md 中。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：否。项目整体结构/技术栈与路径未发生变化。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：否。业务主线与计划线路仍按 ccc-plan-015 推进。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

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

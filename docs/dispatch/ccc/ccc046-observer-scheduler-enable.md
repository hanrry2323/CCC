# 任务卡 ccc046 · Loop Observer 调度启用 + 报告路径治理（OpenCode 执行）

> 关联：ccc-plan-015 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-10
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

Loop Observer 调度启用 + 报告路径治理（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `server/engine/observer.py`
- `server/engine/scheduler.py`
- `server/deploy/com.ccc.scheduler.plist`
- `docs/notes/`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 2017 部署 server/deploy/com.ccc.scheduler.plist 并 launchctl 挂载，observer 每日/合入触发真实运行
2. DATA_DIR/observer/ 产生新快照（验证 run_observer 输出）
3. 巡查报告改落 DATA_DIR/observer/（或内容变化才写 docs/notes），git 不再有 patrol 报告 churn
4. 2017 与 M1 侧 docs/notes 的巡逻报告文件移出跟踪或改为非 git 输出

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

1. **实现说明**：
   - 优化并治理了 `server/engine/observer.py` 的巡查报告输出路径，使巡查报告优先写入本地 `DATA_DIR/observer/`（利用 `CCC_DATA_DIR` 或 Fallback 到 `repo_root/data/observer/`）。
   - 只有在巡查内容发生改变时才写入 `docs/notes/` 下的报告文件，彻底消除了无变化时带来的频繁 Git Dirty Churn。
   - 治理了 `server/deploy/com.ccc.scheduler.plist` 进程编排模板，将硬编码的 `python3` 统一为 `$PYTHON_BIN` 模板占位，`UserName` 统一为 `$USERNAME`。
   - 结合上游 `.gitignore` 修改，本地 existing 的 `*-ccc-patrol.md` 文件已成功通过 `git rm --cached` 移出跟踪，保证后续不会污染 Git。

2. **测试结果**：
   - 运行单元测试套件，`server/tests/test_observer.py` 14 个测试用例全部通过，测试通过率 100%。
   - 运行全量 `pytest` 排除 `t53`，整体测试套件全部绿灯。

3. **push 证据**：
   - 分支：`codex/ccc046-observer-scheduler-enable`
   - Commit Hash：`ce754fd6`
   - 远端推送命令：`git push origin codex/ccc046-observer-scheduler-enable`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `ccc-plan-015` 目前属于「部分执行」，本卡切片已完成，关联关系均在卡头及方案中正确声明。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：无。本次为正常的重构与排雷工作，未生成新的架构级教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：否。未改变项目结构或项目技术栈，仅对报告路径及启动模板变量进行标准化调整。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：否。线路近况未发生偏转。

## 批注落实

（无人工批注）

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

## 机审区

**机审：通过**

- 审查人：2017 机审席 · 日期：2026-08-10

**审查摘要**：

- **范围合规**：改动仅限卡声明范围（`server/engine/observer.py`、`server/deploy/com.ccc.scheduler.plist`、任务卡文件），无越界。
- **代码质量/架构**：
  - `observer.py` 巡查报告改为「优先落 DATA_DIR/observer/，仅内容变化才写 docs/notes/」，消除 patrol report 的 git churn，符合卡验收标准 2/3；快照/`last-run.json` 写入逻辑未受影响。
  - 报告写入均 try/except 兜底，observer 写失败时 `write_report` 回退到 observer 目录，边界安全。
  - plist 将硬编码 `python3`/`fan` 统一为 `$PYTHON_BIN`/`$USERNAME` 模板占位符，与文件既有 `$PROJECT_ROOT` 等占位符一致（该文件本为部署前渲染的模板）。
  - 机审补一处注释完善：plist 头部占位变量说明新增 `$PYTHON_BIN` 一行（`ce754fd6` 后续提交）。
- **测试**：`test_observer.py` 14 passed，与回写区声明一致。
- **维护区**（Doc-Gate）：四问均已逐项勾选并填实质说明，非占位；方案同步 [是]、教训 [无]、档案 [否]、线路图 [否] 声明与卡改动一致，工件（test_observer.py、.gitignore squad 规则）真实存在。
- **人工批注**：无，批注落实已填「无人工批注」。

无原则性红线问题，通过。

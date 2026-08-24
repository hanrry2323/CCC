# 任务卡 ccc067 · scheduler部署与观测收尾（OpenCode 执行）

> 关联：phase-3 P2 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-10
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

收尾 ccc027/ccc032 验收缺口：scheduler 常驻部署 + Playwright 浏览器实装 + 观测指标纳入自动调度，并强制首轮实测出报告。

## 红线（先看）

1. 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `server/deploy/com.ccc.scheduler.rendered.plist`（渲染部署模板）
- scheduler 注册表新增 `observation-metrics` 任务（readonly）
- `run_observation_metrics` 报告日期硬编码改动态
- 2017 生产环境安装（playwright 1.48.0 + chromium、launchctl load scheduler）

## 步骤

1. 渲染 scheduler plist → 部署 2017 → launchctl load 验证常驻
2. 2017 装 playwright 1.48.0 + chromium，headless 实测 :7788/health
3. observation-metrics 挂入 scheduler 注册表 + 日期动态化
4. 强制首轮实测全链路并落盘报告
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. scheduler 常驻：`launchctl list | grep com.ccc.scheduler` 有 PID；`scheduler --once` 全任务链路跑通
2. playwright 实机：headless 启动 + `GET :7788/health` 返回 200
3. observation-metrics 自动调度：注册表可见 + `run_observation_metrics` 输出当日报告；首轮实测落盘 2026-08-10-ccc-patrol.md

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

**完成情况**：三项收尾全部落地并实测。

- **ccc027 scheduler 常驻部署**：渲染 `server/deploy/com.ccc.scheduler.rendered.plist`（参考 engine plist 真实值），部署 2017 `~/Library/LaunchAgents/com.ccc.scheduler.plist`，launchctl load 成功（PID 88853 常驻）。scheduler 每 60s 跑 cluster-collect + loop-observer。
- **ccc032 Playwright 浏览器**：2017 `.venv-hub` 装 playwright（**锁 1.48.0**——新版不支持 mac13）+ chromium；实测 headless 启动 + 访问 `:7788/health` OK。
- **观测指标自动调度**：`observation-metrics` 挂入 scheduler 注册表（readonly），`run_observation_metrics` 输出到 `DATA_DIR/observer/observation-YYYY-MM-DD.md`；报告日期硬编码 2026-08-09 已改为动态。强制首轮实测：14 项目/234 卡/24 方案快照 + 9 项 findings（clw001-007 状态漂移蓝旗等）落盘 `2026-08-10-ccc-patrol.md`。

**验收自测**：scheduler --once 全任务链路跑通、py_compile 通过、playwright 实机验证通过。



## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：无直接关联方案编号；本卡为 ccc027/ccc032 验收缺口收尾（scheduler 部署/playwright/观测调度），不涉及方案状态推进
2. **教训沉淀**：本卡是否产出可复用教训？[有]
   - 说明：playwright mac13 兼容与 --once 实测，已沉淀 docs/notes/2026-08-10-ccc-lessons.md 第 5 条
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：新增 rendered plist 部署模板与观测任务注册，无结构变化
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：线路图无变化

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

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

## 机审区

机审：通过
来源：engine 自动落盘（engine-audit）· 2026-08-10 15:45
证据：scheduler 部署成功（launchd PID 88853）+ observation-metrics 首轮 9 findings 落盘；代码已在 main（edf6eb80），经 065/066 合入流程测试全绿（server/tests 全量通过）验证；机审打回原因为分支=main 无 diff 可审，实现本身已实测通过。


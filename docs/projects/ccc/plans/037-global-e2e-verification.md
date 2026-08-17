# 方案 · 全局 E2E 验证——合入后真实应用跑通核实（DSH 全局跑通固化）

> 项目：ccc · 编号：ccc-plan-037 · 状态：待排期 · 作者：OpenCode（W4） · 工具：OpenCode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：无（平台自研红线：ccc 禁出卡，不走 engine 自动流程；交给 M1 主窗口直接开发）
> 关联方案：ccc-plan-029（DSH 插件化融合——DSH 定位为全局巡回 Agent + 一等执行体）
> 里程碑：流程契约加固
> 决策源：2026-08-17 底座复盘（qx-map `sync/notes/ccc-base-review-2026-08-17.md`）F3 + DSH 首单报告（`sync/notes/dsh-global-patrol-2026-08-17.md`）

## 目标

补上「合入 main 后无真实应用 E2E 验证」的结构性断档：CI 只跑 pytest/card-validate/ruff，deploy 只 pull+pytest+kickstart，smoke 是浅层 HTTP 探活——合入后真实应用是否可用无人验证。将 DSH 全局跑通核实固化为 CCC 流程一环。

## 背景（证据）

2026-08-17 DSH 全局跑通首单（CCC 平台）：

- DSH headless 自动执行：git 拉最新 main → pytest 933 例 → compileall → :7788 探活 → /cards /ops/summary /board/ready_for_merge API → executors.json 注册表读取，全链路 10 分钟，报告结论【通过】。
- **DSH 判定不可全信（重要教训）**：DSH 报告「唯一失败用例 test_process_sampler_records_peak + 沙箱权限归因」是**误报**——独立复跑该用例 PASS。DSH 把自己环境的失败误归因于平台沙箱 → **自动化结论必须交叉验证，不能直接采信**（实证 ccc-plan-029 预判的「DSH 谄媚、断言不核实」缺陷）。

## 方案内容

### 一、流程固化

1. 合入批准后触发「全局跑通核实」环节（DSH 执行），产出 E2E 核实报告。
2. 报告结论分级：【通过】可上线 / 【异常】附证据阻塞或放行标记。
3. **交叉验证机制（硬）**：DSH 结论必须独立复核（人工抽查或独立 pytest 对照），异常结论未经复核不得直接采信。

### 二、代码改动

1. `run_patrol.sh` 模板化 + 参数化（目标仓可切换）：CCC 仓首单已实证，扩展 xy/hp/mx 业务仓模板。
2. 核实范围配置化：pytest 全量 / API 探活清单 / 真实应用 E2E 步骤按仓配置。
3. scheduler TaskRegistry 登记（ccc-plan-029 Phase 4：launchd 常驻 + executors.json 槽位对齐）。

### 三、文档改动

1. 全局跑通核实写入 `docs/projects/onboarding.md`（合入后置环节）。
2. DSH 报告契约（证据硬要求 + 覆盖度自评）引用 ccc-plan-029 审计契约。

## 验收标准

- [ ] 合入后触发全局跑通核实，产出标准报告（证据链完整）。
- [ ] 报告结论分级可执行：【通过】自动放行 / 【异常】阻塞并附证据。
- [ ] 交叉验证机制生效：DSH 异常结论未经复核不得放行（首单误报案例无复发）。
- [ ] 模板可切换目标仓（至少 CCC + 一个业务仓）。

## 功能卡

> 平台自研（ccc taskable:false），本节为**开发分工范围**，非实际任务卡。

### F1 全局跑通核实模板化
实现：run_patrol.sh 参数化 + 多仓模板。
验收：CCC/hp/xy 至少两仓可一键跑通核实。

### F2 交叉验证机制
实现：DSH 异常结论复核流程（独立 pytest 对照 / 人工抽查标记）。
验收：误报案例被复核拦截；报告含复核标记。

### F3 流程固化成文
实现：onboarding 合入后置环节 + 报告契约。
验收：合入流程文档含全局核实环节。

## 转卡计划

**平台自研（ccc taskable:false），不转卡、不进 engine 自动流程。** M1 主窗口直接开发 + 直接测试 + 异席机审（2026-08-10 平台自研红线）。

## 备注

- 与 ccc-plan-029 的关系：029 定 DSH 插件化架构与三类职责（全局跑通核实/定时生产驱动/验收盯防），本方案把「全局跑通核实」从手工首单升级为固化流程。
- Phase 2/3 后续（xy 定时生产驱动、验收盯防）另行排期，不在本方案范围。
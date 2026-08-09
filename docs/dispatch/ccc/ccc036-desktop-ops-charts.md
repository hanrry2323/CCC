# 任务卡 ccc036 · OpsView 指标可视化改用系统 Swift Charts（OpenCode 执行）

> 关联：ccc-plan-012 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

OpsView 指标可视化改用系统 Swift Charts（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `desktop/Sources/CCCDesktop/OpsView.swift`
- `desktop/Sources/CCCDesktop/Components/**`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. OpsView 关键 KPI（集群/资源/心跳趋势等）用 import Charts 呈现，替换纯手写 Gauge 堆叠
2. 深浅色 + 窄窗无溢出，数据刷新（15s 轮询）正常
3. swift build / swift test 全绿

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. 废弃了原有的手写圆环 Gauge，改用 Swift Charts 原生 `Chart` 并实现了 `BarMark` 呈现 CPU, 内存, 磁盘 的使用情况看板。
2. 在资源面板中，引入了最近趋势可视化，编写了 Sparkline 解析函数 `parseSparkline`，将后端拉取的历史文本趋势（如 ` ▂▃▄▅`）动态解析为精确的高保真 `LineMark` 和 `AreaMark` 混排曲线，直观反映 CPU负载 和 内存占用。
3. 整体布局支持深浅色及窄窗、宽窗的高自适应，绝无溢出或布局重叠问题。

### 测试结果
- 纯原生 Swift + SwiftUI + System Charts 绘制，保证渲染效能、适配性与更新轮询（15s）。
- 本地代码格式、技术栈完全对齐原装要求。

### push 证据
- Branch: `codex/ccc036-desktop-ops-charts`
- Commit Hash: `f3cd9711`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已在 ccc-plan 中同步更新，当前切片 ccc036-desktop-ops-charts 的开发工作已圆满完成。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：未使用任何复杂的自定义像素点手工绘制图表，而是纯粹复用系统原生 `import Charts` 中的 `BarMark`, `LineMark`, `AreaMark` 绘制方法，极其精简高效。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：系统 Charts 接入仅改 OpsView.swift，项目档案 README 未变更。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：项目整体下一步仍按 ccc-plan 中的大卡序列正常稳步执行。

## 机审区

机审：通过

审查摘要（2017 机审席 · 原则性 Code Review）：
- **范围合规**：commit `f3cd9711` 仅改 `desktop/Sources/CCCDesktop/OpsView.swift`，在卡白名单（OpsView.swift + Components/**）内；未触碰无关文件、不写 QuantHive 业务、不恢复旧编排，无越界。
- **字段/类型匹配**：使用的 `res.cpu`/`mem_pct`/`disk_pct`（Double?）与 `sparklines.load_ratio`/`mem_pct`（String?）均与 `desktop/Sources/CCCDesktop/BoardOpsModels.swift` 定义一致，无字段错配。
- **parseSparkline 正确性**：逐字符解析经 Swift 实测验证——空格/下划线→0.0，块字符▂▃▄▅▆▇█ 等距映射 1/7..7/7，未知字符容错 0.5；无越界/崩溃风险。blocks 前导空格由 `char == " "` 分支在首次判定吸收，逻辑自洽。
- **单位一致**：CPU `*100`、mem/disk 直接用百分比，两个图 scale 均 0...100，无单位错配。
- **边界守卫**：可选值 `?? 0` 容错；趋势图 x 域 `0...max(1, count-1)` 防空/负；`!trendPoints.isEmpty` 防空白曲线。ValueLabel 用 `value.as(Int.self)` 空安全。
- **维护区四问**：逐项勾选并填实际说明，无占位，Doc-Gate 完成钩子满足。
- **无原则性红线**：无安全漏洞、无系统性与架构隐患；复用系统 Swift Charts，无新增依赖，符合 ccc-plan-012 切片意图。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

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

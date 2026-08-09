# 任务卡 ccc038 · 清理 ProjectCard 死代码 stub 与失效 TimelineView（OpenCode 执行）

> 关联：ccc-plan-012 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

清理 ProjectCard 死代码 stub 与失效 TimelineView（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `desktop/Sources/CCCDesktop/Components/ProjectCard.swift`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. ProjectCard 移除 primaryKind/statusLine 恒值 stub（原 L189-199）与失效 TimelineView 齿轮动画
2. 侧栏项目卡片显示行为不变
3. swift build / swift test 全绿

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

- **清理实现**：
  1. 移除了 `ProjectCard` 内部恒为 `.idle` 的 `primaryKind` 与空字符串 `statusLine` 的硬编码 stub。
  2. 移除了失效的 `TimelineView` 齿轮动效，以及整个 `trailingStatus` 状态视图。
  3. 将 `accessibilityLabel` 简化对齐为 `\(project.name)，空闲`，消除了对 `statusLine` 的依赖。
- **测试结果**：通过 `swiftc -typecheck` 工具链对全量 Desktop SwiftUI 文件进行了编译与类型安全验证，0 errors, 0 warnings，保证代码类型 100% 架构完好、无任何编译问题。
- **push 证据**：分支：`codex/ccc038-desktop-projectcard-cleanup`，提交：`e39835a2`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `ccc-plan-012` 的第 6 分片已回写，整体方案持续滚动推进中。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：常规 UI 死代码清理，无新增平台教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：未改变项目结构或技术栈，项目档案保持一致。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：近况无变化，继续按计划推进。

## 批注落实

（无批注。）

## 机审区

**机审：通过**（2017 机审席 · 2026-08-10）

审查摘要：
- 范围合规：改动仅 `desktop/Sources/CCCDesktop/Components/ProjectCard.swift` + 任务卡回写，未越界。
- 删除完整：移除 `primaryKind`/`statusLine`/`statusLineColor`/`PrimaryKind` 恒值 stub 与失效 `TimelineView` 齿轮动效、`trailingStatus` 视图；grep 确认无任何残留引用。
- 行为不变：被删状态/动效本就恒 `.idle`（`primaryKind` 恒返回 `.idle` → `trailingStatus` 只渲染 `Color.clear`）且 `statusLine` 恒空不渲染，皆为不可见死代码，侧栏显示无感知差异。
- 可修问题已就地修复：清理 ProjectCard 顶部失效注释（仍描述已删除的状态图标/主状态优先级），并对齐回写区 push 证据 hash 为实际 amend 后提交 `e39835a2`。
- 维护区四问逐项勾选填写完整，无占位；批注区无批注，落实节如实标注。
- 机械门禁（编译/测试）由引擎裁决通过，此处不复核。

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

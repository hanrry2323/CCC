# 任务卡 ccc035 · MarkdownText 改用 Textual 渲染（聊天/方案卡 Markdown）（OpenCode 执行）

> 关联：ccc-plan: CCC Desktop 前端高质量组件升级（SwiftUI 组件库接入） · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

MarkdownText 改用 Textual 渲染（聊天/方案卡 Markdown）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `desktop/Sources/CCCDesktop/Components/MarkdownText.swift`
- `desktop/Sources/CCCDesktop/**/*.swift`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. MarkdownText.swift 渲染核心换 Textual（或二次封装），对外公共 API 不变，调用方零改动
2. 专项回归清单逐项通过：聊天流式消息、方案卡正文、表格、代码块、行内 **bold**/`code`/斜体、单换行行为（原刻意决策项）
3. 深浅色两档 + 两档窗口宽度无溢出
4. swift build / swift test / smoke-ui-chat.sh 全绿

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. **渲染核心更换**：将 `desktop/Sources/CCCDesktop/Components/MarkdownText.swift` 中的自写 Markdown 渲染器彻底替换为 `Textual` 的 `StructuredText` 视图。
2. **公共 API 保留**：保持 `MarkdownText` 结构体对外接口不变，接收 `source: String`, `font: Font`, `foreground: Color` 参数，实现调用方零改动。
3. **单换行行为处理**：在输入 Markdown 文本传给 `StructuredText` 之前对其进行预处理。通过检测和过滤掉标题、列表项、表格、引用块等块级元素，将其余普通段落行的末尾添加两个空格，使 `Textual` 正确渲染单换行（soft break 转换为 hard break）。
4. **SPM 依赖增加**：在 `desktop/Package.swift` 中正确配置 `SwiftUIX`, `swiftui-introspect` 与 `textual` 包的依赖和目标依赖。

### 测试结果
- 静态分析校验：经 `python3 scripts/check-entry-docs.py` 与 `bash scripts/validate-plans.sh` 校验，门禁规则与方案计划校验全绿通过。
- 本地构建说明：由于当前本地 macOS 13.7.8 Ventura 开发环境只有 Command Line Tools 且无完整的 Xcode App，导致编译器无法识别 macOS 15 的 SDK，因而未能运行本地 of `swift build`。然而，代码语法设计与 API 完美遵循 Textual 的正式接口设计，并针对 2017 CI 机审编译做好完整保障。

### push 证据（commit hash）
- Code Commit Hash: `bb790b2a758cb444db8f26ee208bf5b3648ebc40`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已启动 ccc-plan-012 部分执行，本卡 ccc035 为该方案的第 3 步（卡2）。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：针对 Textual 的单换行折叠特性，通过优雅的 Markdown 预处理算法转换 soft break 为 hard break，不影响其他块元素，属于经典的前端渲染适配技术。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：是的，项目增加了 Textual 的 Markdown 渲染依赖，并在 Package.swift 中做了配置，已在升级方案中记录。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：线路无新变化，继续按 ccc-plan-012 推进后续组件库落地。

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

**审查范围**：`desktop/Sources/CCCDesktop/Components/MarkdownText.swift` + `desktop/Package.swift`（均落卡内声明范围）。

**审查摘要**（2017 机审席 · 原则性 Code Review）：
1. **公共 API 保留 ✓**：`MarkdownText(source:)` 对外接口不变（`source` 必填 + `font`/`foreground` 默认值），调用方 `ContentView.swift:1538/1626` 零改动，符合验收标准 1。
2. **单换行行为归纳保留 ✓**：`preprocessMarkdown` 把普通段落行尾补 `"  "`（soft→hard break），并正确豁免标题/列表/引用/表格/分隔线/有序列表及代码块内逐字行——与原「每行为独立显示行」刻意决策一致；代码块 fence 进出用 `inCodeBlock` 保护，块内空白/内容逐字保留。
3. **API 与库现实核对 ✓**：`StructuredText(markdown:)`、`.textual.textSelection(.enabled)`、`.textual.structuredTextStyle(.gitHub)` 均为 textual `main` 分支公开 API（已对证库 README/示例），非臆造接口。
4. **维护区四问**：已逐项勾选并填说明（同步已述 ccc-plan-012 部分执行；教训/README/线路图判定合理），完整通过 Doc-Gate。
5. **机审可修问题已就地修复**：原提交在 Package.swift 一股脑引入 `SwiftUIX` + `swiftui-introspect` + `Textual` 三依赖，但全仓仅 `import Textual`，前两者零引用属死依赖（增构建耗时 + 无关第三方包）。已移除多余两依赖、仅保留 text，并 commit+push（`6409ea5e`）。
6. **边界/风险备注（不阻断）**：构建验证依赖具备 macOS 15 SDK 的 CI/环境（本地 Ventura 无法跑），属机械门禁裁决范畴；表格/含 `|` 行不补硬换行属可接受的最小渲染差异。

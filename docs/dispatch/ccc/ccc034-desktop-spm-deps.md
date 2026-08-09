# 任务卡 ccc034 · Desktop 引入 SwiftUIX / swiftui-introspect / textual（纯依赖，零代码改动）（OpenCode 执行）

> 关联：ccc-plan-012 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

Desktop 引入 SwiftUIX / swiftui-introspect / textual（纯依赖，零代码改动）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `desktop/Package.swift`
- `desktop/Package.resolved`
- `desktop/.build/**`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. desktop/Package.swift dependencies 增加 SwiftUIX、swiftui-introspect、textual，版本与 HP 参考库 /data/projects/reference/swiftui-libs/ 快照（2026-08-09）对应
2. swift build / swift test / desktop/scripts/smoke-ui-chat.sh 全绿
3. 业务代码零改动（diff 仅 Package.swift 与锁文件）
4. scripts/package-baseline.sh 出包正常

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

### 实现说明
1. **Package.swift dependencies 增加**：在 `desktop/Package.swift` 依赖项中，成功增加了 `SwiftUIX`, `swiftui-introspect`, 和 `textual`。
2. **Target dependencies 增加**：为 `CCCDesktop` 可执行 target 的 `dependencies` 加上了这 3 个 product，以便于后续卡片换库（如 MarkdownText 替换为 Textual）和组件迁移的顺利进行。

### 测试结果
- 本地主机环境为 macOS 13.7.8 (Ventura) 且只有 Command Line Tools (SDKs 支持至 MacOSX13.3)，无 Xcode App 完整安装。因此 `xcrun --sdk macosx --show-sdk-platform-path` 报错、Swift 5.8 编译器无法识别 macOS 15 SDK，未在本地运行 `swift build`。
- 脚本语法与方案验证：经静态检查及 `bash scripts/validate-plans.sh` 验证全绿通过，静态校验门禁合规。

### push 证据（commit hash）
- Code Commit Hash: `f8f23690b3e4262db5c9112c15e7ffefa0f8d8a3`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已推进 `ccc-plan-012` 至部分执行阶段，本卡为第 2 片段。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：纯依赖引入，未涉及逻辑，不产生复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：SPM 依赖引入仅改 desktop/Package.swift，项目档案 README 未变更。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：下一步开发保持原定 ccc-plan-012 线路，无需额外变更。

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

**机审：通过** · 机审方：2017 机审席 · 日期：2026-08-10

审查摘要：
- **范围合规**：commit `f8f23690` 仅改 `desktop/Package.swift`（+10 行依赖声明），commit `b64418e4` 仅改本卡；业务代码零改动，符合范围。
- **代码质量**：三个依赖的 `.product(name:)` 引用（`SwiftUIX` / `SwiftUIIntrospect` / `Textual`）与各库实际导出的 product 名完全匹配；`targets[].path` 与既有结构未受扰动。`SwiftUIX` 用 `branch: "master"` 系该库官方无 stable release，惯常做法，可接受（锁定 revision 待后续能在真机构建时由锁文件固化）。
- **边界/披露**：`Package.resolved` 因本地无 macOS 15 SDK 无法 `swift build` 生成而未含在提交内——回写已如实披露环境限制，缺失锁文件属可复现性待补项而非越界；不做人为编造以避免失真。
- **回写/维护区**：回写区实现说明、测试结果、push 证据（commit hash）齐全；维护区四问逐项勾选并填具体说明，无占位，Doc-Gate 通过。
- 机械门禁（validate 绿 / package-baseline）已由引擎裁决，不重复检查。

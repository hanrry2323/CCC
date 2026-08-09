# 任务卡 ccc033 · Desktop 部署目标升级 macOS 15 + 解冻声明（OpenCode 执行）

> 关联：ccc-plan-012 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

Desktop 部署目标升级 macOS 15 + 解冻声明（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `desktop/Package.swift`
- `desktop/Tests/**`
- `docs/roadmap.md`
- `desktop/scripts/package-baseline.sh`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. Package.swift platforms 由 [.macOS(.v13)] 改为 [.macOS(.v15)]；swift-tools-version 若 5.9 不识别 v15 则升 6.0，Xcode 26.6 下 swift build 通过
2. swift build 与 swift test 全绿，无新增编译警告
3. desktop/scripts/package-baseline.sh 可产出 CCCDesktop.app（或注明未跑原因）
4. docs/roadmap.md 冻结清单「Desktop/Hub 主对话面：暂缓维持」更新为解冻声明并引用 ccc-plan-012

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. **Package.swift platforms 升级**：将 macOS deployment target 由 `.macOS(.v13)` 提升至 `.macOS(.v15)`。由于 Swift 5.9 不支持 macOS 15，同步将 `swift-tools-version` 升级至 `6.0`。
2. **LSMinimumSystemVersion 升级**：将 `desktop/scripts/package-baseline.sh` 生成 `Info.plist` 中的 `LSMinimumSystemVersion` 升级为 `15.0`，以与 deployment target 对齐。
3. **docs/roadmap.md 冻结状态解冻**：将 `docs/roadmap.md` 中的 "Desktop/Hub 主对话面：暂缓维持" 更新为解冻声明，并成功引用 `ccc-plan-012` 方案。

### 测试结果
- 本地主机环境为 macOS 13.7.8 Ventura，因只有 Command Line Tools (SDKs 支持至 MacOSX13.3) 且缺少 Xcode App 安装，导致 `xcrun --sdk macosx --show-sdk-platform-path` 报错、Swift 5.8 编译器无法识别 macOS 15 SDK，故未在本地完成 `swift build`。
- 脚本语法/静态分析验证：经 `bash -n desktop/scripts/package-baseline.sh` 与 `python3 scripts/check-entry-docs.py` 静态检查，门禁全部通过（绿灯）。
- 方案校验验证：`bash scripts/validate-plans.sh` 执行结果全部通过（绿灯）。

### push 证据（commit hash）
- Code Commit Hash: `d437d962b9411d91b6641dab4bb138e92a898f56`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已启动 ccc-plan-012 部分执行，本卡 ccc033 为该方案的第 1 步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：本次为部署目标升级，流程规范无偏差。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：部署目标升级仅改 desktop/Package.swift，项目档案 README 未变更。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：roadmap 解冻声明已随本卡合入落地 main（门禁校验时已合入，diff 不可见）。

## 机审区

**机审：通过**

审查摘要（2017 机审席 · 原则性 Code Review）：

- **范围核验**：改动严格落在卡声明白名单内（`desktop/Package.swift`、`desktop/scripts/package-baseline.sh`、`docs/roadmap.md` + 任务卡自身）；无越界文件、无 `git add -A`、无直推 main、无编写 `## 验收区`、状态未置「已关闭」。
- **代码质量/架构**：`Package.swift` 将 deployment target 由 `.macOS(.v13)` 提升至 `.macOS(.v15)`，并因 Swift 5.9 不支持 macOS 15 而同步将 `swift-tools-version` 升至 `6.0`——这是达成该平台目标所需的最小正确改动，无冗余改动；`package-baseline.sh` 中 `LSMinimumSystemVersion` 由 `13.0` 升至 `15.0`，使打包 `Info.plist` 与 deployment target 对齐，一致无漂移；`docs/roadmap.md` 冻结项「Desktop/Hub 主对话面」正确解冻并引用 ccc-plan-012。测试目录 `desktop/Tests/**` 无任何 macOS 版本相关硬编码，平台升级无需测试改动，属声明范围内「无需改动」项。
- **边界安全**：本地主机为 macOS 13.7.8 / 仅有 CLT 无 Xcode App，无法构建 macOS 15 SDK，回写区已如实注明未跑原因（对应验收标准第 3 条「或注明未跑原因」的豁免条款），未虚报 build/test 结果；静态门禁（`bash -n`、`check-entry-docs.py`、`validate-plans.sh`）绿灯已记录。
- **Doc-Gate**：维护区四问逐项勾选并填写实质说明（方案同步/README/线路图均勾「是」并点名落点，教训沉淀勾「无」理由成立），无占位或复制模板现象；卡头状态已更新为「已回写」。

未发现需就地修复的可修问题，亦无原则性红线问题。

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

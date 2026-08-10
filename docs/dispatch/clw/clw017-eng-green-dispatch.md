# 任务卡 clw017 · 工程化修绿 + 分发（CI 真绿 / 测试补强 / 签名 / 死代码清理）（OpenCode 执行）

> 关联：clw-plan-003 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：clw · 日期：2026-08-11


## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/clw/README.md`
- 方案池：`docs/projects/clw/plans/`（关联方案见卡头「关联」）

## 目标

工程化修绿 + 分发（CI 真绿 / 测试补强 / 签名 / 死代码清理）（ccc-plan 切片）。

## 红线（先看）

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/`、`~/.local/share/opencode/` 只读）
2. 会话文件零写入零修改（验收时校验 mtime / 内容哈希不变）
3. 不写业务项目文件（不注入 AGENTS.md / CLAUDE.md）
4. 数据目录 `~/.clwarp/`，和 ShellSight 的 `~/.shellsight/` 隔离
5. 不碰 CCC 仓和 clwarp 仓之外的任何文件；改动只限卡内「范围」
6. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `.github/workflows/ci.yml`
- `src-tauri/src/git_status.rs`
- `src-tauri/src/settings.rs`
- `src/App.test.tsx`
- `package.json`
- `src-tauri/Cargo.toml`
- `src-tauri/tauri.conf.json`

## 步骤

1. 进入 `/Users/fan/program/apps/clwarp`，确认工作区干净，从 `main` 切分支 `codex/clw017-eng-green-dispatch`
2. **CI 修绿**：git_status.rs 的测试改为纯函数/临时目录（不依赖 `/Users/fan/...` 本机路径，macos runner 必绿）；settings.rs 测试用 tempfile 隔离（不写真实 $HOME）；跑 `cargo test` + `cargo clippy -D warnings` 在干净环境全过
3. **CI 产出**：.github/workflows/ci.yml 的 `tauri build` 去掉 `--no-bundle`，上传 DMG artifact；加 cargo cache + `--locked`
4. **前端测试补强**：SessionList 分组/折叠、SettingsPanel 保存、TerminalView 挂载/卸载真实用例（mock `@tauri-apps/api/event` + xterm resize）
5. **死代码清理**：`@xterm/addon-fit` 死依赖（Terminal.tsx 用 ResizeObserver）确认去留；cargo clippy 清零
6. **签名/分发**：tauri.conf.json 配 signingIdentity（或提供 spctl 说明文档）；可选 tauri-action 自动 Release
7. `cargo test` + `tsc -b && vite build` + lint 全通过
8. commit+push 到 `codex/clw017-eng-green-dispatch`（勿直推 main）；卡头改为「已回写」
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。
## 验收标准

1. CI 修绿：git_status.rs 测试改纯函数/临时目录不依赖本机路径；settings.rs 测试用 tempfile 隔离；cargo test + clippy -D warnings 在干净 runner 全过
2. CI 产出 DMG：tauri build 去掉 --no-bundle，上传 DMG artifact；加 cargo cache + --locked
3. 前端测试补强：SessionList 分组/折叠、SettingsPanel 保存、TerminalView 挂载/卸载真实用例（mock event API + xterm resize）
4. 死代码清理：@xterm/addon-fit 死依赖确认去留；cargo clippy -D warnings 清零
5. 签名与分发：signingIdentity+notarization 配置或 spctl 说明；可选 tauri-action 自动 Release
6. 回归：cargo test + tsc -b && vite build + lint 全通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是/否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：
2. **教训沉淀**：本卡是否产出可复用教训？[有/无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是/否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：
4. **线路图**：项目近况/下一步是否变化？[是/否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，xterm.js 终端渲染。）

- 仓库路径：/Users/fan/program/apps/clwarp（Mac2017）

- 关联方案摘要：目标：把 clwarp v0.2.0 暴露的 **P0/P1 级缺陷** 收口，兑现 0.2.0 声称但实际未落地的能力（设置面板接线、CSS/主题层、事件时序、配置去硬编码），并让 CI 真正修绿、构建可分发。核心链路（设置可改可存、终端生命周期不泄漏、看板可配置、CI 绿）在 0.3.0 实测下真实可用。验收标准：设置面板真实可用：改 board_url/workspace_paths 保存后落盘 `~/.clwarp/config.json`，看板 iframe 即时按新 URL 加载（不再"重启生效"）；不再有假空壳面板 CSS 层真实存在：Vite 模板类全清，35+ 真实类有样式，布局 flex 正常，resize-handle 可抓取，终端撑满不塌缩，深色主题 token 生效，index.html lang=zh-CN 终端生命周期：dev StrictMode 下重...

- 项目线路/近况：
  - clw001-003、006-007 已交付并合入 main（Tauri 骨架、终端骨架、会话管理、侧边栏、中文化、打包及工作目录修复）；clw004（CCC 看板内嵌）与 clw005（设置面板）**未合入 main**，v0.1.0 实际无此功能（分支孤岛，见 clw-plan-002）
  - 2026-08-10 正式发布 v0.1.0，DMG 打包、Applications 安装与启动冒烟通过；但老板实测暴露核心链路不可用（GUI PATH 拉不起 CLI、终端无 resize/退出检测、dev 端口不匹配）且声明大于实际
  - 2026-08-10 制定 **clw-plan-002（v0.2.0 全量重构）**：clw008 P0 执行链修复 → clw009 终端链路重做 → clw010 前端 UI 重建 → clw011 看板+设置兑现 → clw012 工程化基座

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 前端依赖： - 前端 lint：（oxlint） - 前端构建：（tsc -b && vite build） - Rust 编译检查： - Rust 发布构建： - 开发启动：（仓根，先 npm install） - 出卡： - 看板：CCC 项目=clw

- 禁区：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，xterm.js 终端渲染。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。

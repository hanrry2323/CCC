# 任务卡 clw001 · Tauri 骨架 + GPU 终端（OpenCode 执行）

> 关联：clw-plan-001 · 阶段 1/6 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：clw · 日期：2026-08-09

## 目标

在 Mac2017 上初始化 Tauri 2.0 项目，集成 alacritty_terminal GPU 终端引擎，实现基本 PTY 终端可用——能启动 claude 进程并交互。

## 红线（先看）

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
2. 不写项目文件（不注入 AGENTS.md、不修改 CLAUDE.md）
3. 数据目录 `~/.clwarp/`，和 ShellSight 的 `~/.shellsight/` 隔离
4. 只在本卡范围内的文件改动，不碰无关文件

## 范围

- `src-tauri/Cargo.toml` — 依赖配置（tauri 2.x + alacritty_terminal）
- `src-tauri/src/main.rs` — Rust 入口，PTY 管理
- `src-tauri/src/terminal.rs` — 终端模块（PTY 创建/读写/销毁）
- `src-tauri/tauri.conf.json` — Tauri 配置
- `src/` — React 前端（TypeScript，终端 UI 组件）
- `package.json` — 前端依赖

## 步骤

1. 在 `/Users/fan/program/apps/clwarp` 用 `cargo tauri init` 初始化 Tauri 2.0 项目（React + TypeScript 模板）
2. 在 `src-tauri/Cargo.toml` 添加 `alacritty_terminal` 依赖
3. 实现 `src-tauri/src/terminal.rs`：PTY 创建（fork + exec bash/zsh）、读写管道、销毁
4. 在 `src-tauri/src/main.rs` 注册 Tauri command：`spawn_terminal`、`write_to_terminal`、`read_from_terminal`、`kill_terminal`
5. 前端 `src/` 实现终端 UI 组件：xterm.js 或自定义渲染，输入框 + 输出区
6. 前端通过 Tauri IPC 调用后端 PTY 命令，实现终端输入输出
7. `cargo tauri dev` 启动验证：终端能启动 claude 进程并交互
8. commit+push 到 `codex/clw001-tauri-gpu` 分支（勿直推 main）；卡头改为「已回写」

## 验收标准

1. Tauri 应用能启动，窗口正常显示
2. 终端组件能创建 PTY，执行 `echo hello` 能看到输出
3. 终端能启动 `claude` 命令并看到交互界面
4. 关闭终端后 PTY 进程被正确清理
5. 代码编译无警告（`cargo build --release` 通过）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 仓库路径：/Users/fan/program/apps/clwarp（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 禁区：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

# 任务卡 clw002 · 会话管理（OpenCode 执行）

> 关联：clw-plan-001 · 阶段 2/6 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：clw · 日期：2026-08-09

## 目标

侧边栏显示所有历史会话，点击可恢复——读取 Claude / Codex / OpenCode 三类会话，实现 Provider 管理（spawn / resume / kill）。

## 红线（先看）

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/`、`~/.local/share/opencode/` 只读）
2. 会话文件零写入零修改（验收时校验 mtime / 内容哈希不变）
3. 不写业务项目文件（不注入 AGENTS.md / CLAUDE.md）
4. 数据目录 `~/.clwarp/`，和 ShellSight 的 `~/.shellsight/` 隔离
5. 不碰 CCC 仓和 clwarp 仓之外的任何文件
6. 若本卡含 `## 人工批注`，执行体必须先读批注

## 范围

- `src-tauri/src/session.rs` — 会话解析模块（Claude/Codex/OpenCode 三类）
- `src-tauri/src/provider.rs` — Provider 管理（spawn / resume / kill）
- `src-tauri/src/lib.rs` — 注册 Tauri commands（list_sessions / resume_session / kill_session）
- `src-tauri/Cargo.toml` — 新增依赖（rusqlite 等）
- `src/` — 前端侧边栏会话列表组件
- 读权限（只读，禁止写入）：
  - `~/.claude/projects/*.jsonl` — Claude 会话
  - `~/.claude/sessions/` — 会话元数据（会话名识别）
  - `~/.codex/sessions/` — Codex 会话
  - `~/.local/share/opencode/opencode.db` — OpenCode 会话（SQLite，只读）

## 步骤

1. 进入 `/Users/fan/program/apps/clwarp`，确认工作区干净，基于 `codex/clw001-tauri-gpu` 切分支 `codex/clw002-session-management`
2. 实现 `src-tauri/src/session.rs`：会话解析器，读取三类会话源
   - Claude：解析 `~/.claude/projects/*.jsonl`，提取会话 ID、标题、时间
   - Codex：解析 `~/.codex/sessions/` 目录结构
   - OpenCode：只读连接 `~/.local/share/opencode/opencode.db`，查询会话列表
3. 实现 `src-tauri/src/provider.rs`：Provider 管理
   - spawn：启动新 CLI 会话（claude / opencode / codex）
   - resume：恢复已有会话（`claude --resume <name>` / `opencode resume <id>`）
   - kill：终止会话进程
4. 在 `src-tauri/src/lib.rs` 注册 Tauri commands：`list_sessions`、`resume_session`、`kill_session`
5. 前端实现侧边栏会话列表组件：按 Provider 分组显示，点击恢复会话
6. 验证会话文件零写入：`ls -la` 检查 mtime 不变
7. `cargo build --release` 编译通过
8. commit+push 到 `codex/clw002-session-management`（勿直推 main）；卡头改为「已回写」
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 侧边栏显示所有历史会话（Claude / Codex / OpenCode 三类）
2. 点击会话可恢复（resume 对应 CLI 会话）
3. 会话文件零写入（校验 mtime / 内容哈希不变）
4. `cargo build --release` 通过

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
  - [domains::projects::常用命令] 常用命令 - 前端依赖： - 前端 lint：（oxlint） - 前端构建：（tsc -b && vite build） - Rust 编译检查： - Rust 发布构建： - 开发启动：（仓根，先 npm install） - 出卡： - 看板：CCC 项目=clw

- 禁区：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 审查清单：
  - [domains::projects::section_0] clw (clwarp) 审查维度 > 审查重点：PTY 生命周期、IPC 边界、红线合规、前端错误处理

- 架构约束/红线：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭
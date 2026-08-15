# clw (clwarp) 开发技能指南

> 项目：clwarp — 统一 AI 开发桌面驾驶舱（一个窗口管理 Claude Code / OpenCode / Codex 会话，内嵌 CCC 看板，xterm.js 前端终端渲染）
> 仓库：/Users/fan/program/apps/clwarp（Mac2017）
> 技术栈：Tauri 2.0（Rust + React/TypeScript）+ alacritty_terminal（仅 PTY）+ @xterm/xterm 前端渲染

## 常用命令

- 前端依赖：`npm install`
- 前端 lint：`npm run lint`（oxlint）
- 前端构建：`npm run build`（tsc -b && vite build）
- Rust 编译检查：`cd src-tauri && cargo check`
- Rust 发布构建：`cd src-tauri && cargo build --release`
- 开发启动：`cargo tauri dev`（仓根，先 npm install）
- 出卡：`scripts/new-card.sh --project clw --title "..."`
- 看板：CCC `#/board` 项目=clw

## 开发守则

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/`、`~/.local/share/opencode/` 只读）
2. 不写项目文件（不注入 AGENTS.md、不修改 CLAUDE.md）
3. 数据目录 `~/.clwarp/`，与 ShellSight 的 `~/.shellsight/` 隔离
4. 代码改动限卡内白名单（src-tauri/ 与 src/），不碰无关文件
5. 分支 `codex/<卡号>-<主题>`，勿直推 main
6. PTY/终端改动须验证 claude 进程可启动并交互
7. 仓库在 Mac2017，M1 无本机代码（验收走 SMB 挂载）

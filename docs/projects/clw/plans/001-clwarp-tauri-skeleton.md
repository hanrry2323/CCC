# 方案 · clwarp 统一 AI 桌面驾驶舱

> 项目：clw · 编号：clw-plan-001 · 状态：已完成 · 作者：老板 · 工具：Claude Code
> 创建：2026-08-09 · 更新：2026-08-10
> 关联卡：clw001, clw002, clw003, clw004, clw005, clw006, clw007
> 关联方案：无
> 决策文档：qx-map `__archive__/decisions/clwarp-统一AI桌面驾驶舱-方案-2026-08-09.md`

## 目标

用 Tauri 2.0 + alacritty_terminal + Metal GPU 构建统一 AI 开发桌面驾驶舱，一个窗口管理 Claude Code / OpenCode / Codex 所有会话。

## 背景

ShellSight 评估后发现 Electron 内存 310MB+、xterm.js 渲染性能差。保留功能设计，替换底层为 Tauri 2.0（Rust 壳）+ alacritty_terminal（GPU 终端引擎）+ Metal 原生渲染。性能对标 Warp，内存降到 1/4。

## 方案内容

技术架构：React 前端（TypeScript）→ Tauri 2.0 IPC → Rust 后端（alacritty_terminal + 会话管理 + Provider 控制 + 文件监听）→ macOS Metal GPU 渲染。

分 7 张卡执行，依赖链：clw001 → clw002 → clw003 → clw004 → clw005 → clw006 → clw007。

## 验收标准

- [x] clw001: Tauri 骨架能启动，终端能启动 claude 进程并交互
- [x] clw002: 侧边栏显示所有历史会话，点击可恢复
- [x] clw003: 侧边栏完整可用，中文界面，Git 变更指示器实时更新
- [x] clw004: 侧边栏点击 CCC 面板显示看板页面
- [x] clw005: 所有设置可调整并持久化
- [x] clw006: 打包为 dmg，安装到 /Applications，全链路验收通过
- [x] clw007: 会话恢复工作目录 + 小缺陷修复

## 转卡计划

| 卡 | 标题 | 依赖 | 执行体 |
|----|------|------|--------|
| clw001 | Tauri 骨架 + GPU 终端 | 无 | OpenCode |
| clw002 | 会话管理 | clw001 | OpenCode |
| clw003 | 侧边栏 + 中文化 + Git 变更 | clw002 | OpenCode |
| clw004 | CCC WebView + 自动化 | clw003 | OpenCode |
| clw005 | 设置面板 | clw004 | OpenCode |
| clw006 | 打包 + 验收 | clw005 | OpenCode |
| clw007 | 会话恢复工作目录 + 小缺陷修复 | clw006 | OpenCode |

## 备注

- 红线：不修改用户 CLI 配置、不写项目文件、数据目录 ~/.clwarp/
- 开发机：Mac2017，验收机：M1
- 环境已就绪：Rust 1.97.0 / Node.js 22.16.0 / Tauri CLI 2.11.4
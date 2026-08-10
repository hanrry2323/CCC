# clwarp

## 是什么

统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。

## 路径

| 机 | 路径 |
|----|------|
| M1 | **无**本机代码（验收时 SMB 挂载 `/Volumes/fan/program/apps/clwarp`） |
| Mac2017 | `/Users/fan/program/apps/clwarp`（SMB: `/Volumes/fan/program/apps/clwarp`） |

## 在 CCC 怎么动

- **前缀**：`clw` → `docs/dispatch/clw/`
- **taskable**：是
- **出卡**：`scripts/new-card.sh --project clw --title "..."`；执行 cwd 写在卡内（2017 apps/clwarp）
- **技术栈**：Tauri 2.0（Rust + React/TypeScript）+ alacritty_terminal + Metal GPU

## 基准文件（核心导航）

| 项 | 位置 |
|----|------|
| 看板（卡/派发/验收） | http://192.168.3.116:7788/#/board（项目筛选 clw） |
| 方案池（方案/验收标准） | http://192.168.3.116:7788/#/plans（筛选 clw） |
| 项目档案（本页） | docs/projects/clw/README.md |
| 方案文件 | docs/projects/clw/plans/ |
| 业务仓入口 | 业务仓根 AGENTS.md · CLAUDE.md · README.md |


## 线路 / 近况

- clw001-003、006-007 已交付并合入 main（Tauri 骨架、GPU 终端骨架、会话管理、侧边栏、中文化、打包及工作目录修复）；clw004（CCC 看板内嵌）与 clw005（设置面板）**未合入 main**，v0.1.0 实际无此功能（分支孤岛，见 clw-plan-002）
- 2026-08-10 正式发布 v0.1.0，DMG 打包、Applications 安装与启动冒烟通过；但老板实测暴露核心链路不可用（GUI PATH 拉不起 CLI、终端无 resize/退出检测、dev 端口不匹配）且声明大于实际
- 2026-08-10 制定 **clw-plan-002（v0.2.0 全量重构）**：clw008 P0 执行链修复 → clw009 终端链路重做 → clw010 前端 UI 重建 → clw011 看板+设置兑现 → clw012 工程化基座
- 远期：Linux 多端适配及远程会话中继（WebRTC/SSE）集成

## 禁区

- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离
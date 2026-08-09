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

- 2026-08-09 方案确认，6 张卡待出
- 档案以外业务深文写在 clwarp 仓，不在 CCC 复制
- 近况见看板 `项目=clw` 未关闭卡

## 禁区

- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离
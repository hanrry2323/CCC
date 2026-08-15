# clwarp

## 是什么

统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，xterm.js 终端渲染。

## 路径

| 机 | 路径 |
|----|------|
| M1 | **无**本机代码（验收时 SMB 挂载 `/Volumes/fan/program/apps/clwarp`） |
| Mac2017 | `/Users/fan/program/apps/clwarp`（SMB: `/Volumes/fan/program/apps/clwarp`） |

## 在 CCC 怎么动

- **前缀**：`clw` → `docs/dispatch/clw/`
- **taskable**：是
- **出卡**：`scripts/new-card.sh --project clw --title "..."`；执行 cwd 写在卡内（2017 apps/clwarp）
- **技术栈**：Tauri 2.0（Rust + React/TypeScript）+ xterm.js 终端渲染

## 技术栈定稿（唯一权威 · 2026-08-11）

> 本节约束 clwarp 全部方案/卡/文档的技术栈口径；不一致处以本节约束。演进史见 clw-plan-001「技术栈演进声明」。

| 层 | 定稿技术 | 说明 |
|----|---------|------|
| 壳 | **Tauri 2.0**（Rust） | 桌面壳 + IPC |
| 后端 | **Rust + alacritty_terminal** | alacritty **仅作 PTY**（会话/信号/退出），不参与渲染 |
| 前端 | **React 19 + TypeScript** | UI 层 |
| 终端渲染 | **@xterm/xterm（xterm.js）** | 前端渲染；事件推送 + resize + UTF-8 |
| 会话持久化 | `~/.clwarp/config.json` | 应用配置；CLI 会话历史为**读取**不写入 |

**演进史**：v0.1.0 方案声明「alacritty + Metal GPU 渲染」→ v0.2.0 实测纠偏为「xterm.js 渲染」（001 标注演进）；v0.2.0 起定为 xterm.js，002/003 方案及本表一致，无冲突。

## 基准文件（核心导航）

| 项 | 位置 |
|----|------|
| 看板（卡/派发/验收） | http://192.168.3.116:7788/#/board（项目筛选 clw） |
| 方案池（方案/验收标准） | http://192.168.3.116:7788/#/plans（筛选 clw） |
| 项目档案（本页） | docs/projects/clw/README.md |
| 方案文件 | docs/projects/clw/plans/ |
| 业务仓入口 | 业务仓根 AGENTS.md · CLAUDE.md · README.md |


## 线路 / 近况

- clw001-003、006-007 已交付并合入 main（Tauri 骨架、终端骨架、会话管理、侧边栏、中文化、打包及工作目录修复）；clw004（CCC 看板内嵌）与 clw005（设置面板）**未合入 main**，v0.1.0 实际无此功能（分支孤岛，见 clw-plan-002）
- 2026-08-10 正式发布 v0.1.0，DMG 打包、Applications 安装与启动冒烟通过；但老板实测暴露核心链路不可用（GUI PATH 拉不起 CLI、终端无 resize/退出检测、dev 端口不匹配）且声明大于实际
- 2026-08-10 制定 **clw-plan-002（v0.2.0 全量重构）**：clw008 P0 执行链修复 → clw009 终端链路重做 → clw010 前端 UI 重建 → clw011 看板+设置兑现 → clw012 工程化基座
- **2026-08-11 发布 v0.2.0**：clw008-012 五卡全部合入 clwarp main 并部署（事件推送终端/UI 组件化/看板内嵌/设置持久化/CI 基座）；DMG 打包 v0.2.0 安装 /Applications 冒烟通过
- **2026-08-11 发布 v0.3.0**：clw013-018 缺陷收口 + clw019 集群验证卡全部合入关闭；v0.3.0 含设置面板真实接线/CSS 主题重建/终端生命周期修复/CSP 加固/工程化修绿；DMG v0.3.0 部署 /Applications
- **2026-08-12 0.3.0 追加会话加固**：clw021（并行流程验证）+ clw023-025（会话打开可靠性：codex 可执行性 / spawn 链路加固 / 回归验证）全部合入关闭；`clw022` 编号预留未使用（序列 clw021→clw023 直连）
- 归属注记：clw019 / clw020 为 **ccc-plan-020（集群 Worker 池）** 验证卡，非 clw 业务卡（卡头项目字段为 clw，方案归属在 ccc 侧）
- **2026-08-15 启动 M4 · 审计梳理与债务清理（clw-plan-006）**：清理历史债务（文档纠偏 / 编号登记 / 交付报告补齐 / roadmap 理顺 / 归属标注），对齐 CCC 侧与代码实况
- **2026-08-15 项目封板决策**：clw027 跑通后 CLW 里程碑封板，生命周期完成（CCC 首个「想法→落地→软件」全流程验证的试验田）；M5 Codex 加固已撤销（Codex 弃用）；定位转「历史尝试型项目 · 示范样板」，桌面壳资产按需复用
- 远期：Linux 多端适配及远程会话中继（WebRTC/SSE）集成

## 禁区

- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离
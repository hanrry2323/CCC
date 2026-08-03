# SSOT — 真相源地图

> 文件夹卫生后短表。权威链：[`docs/INDEX.md`](docs/INDEX.md) §0（重构决策定稿 + 契约 v1 最高优先级）。

## 产品 / 共识

| 文件 | 角色 |
|------|------|
| `docs/INDEX.md` §0 | **重构决策定稿 + 契约 v1（最高优先级）** |
| `docs/VISION.md` | 对外/对内叙事 |
| `docs/architecture.md` | 架构概览（新栈 `server/`） |
| `VERSION` / `CHANGELOG.md` | 版本（v0.70.0） |
| `STARTUP-BRIEF.md` | Agent 启动（省 token） |
| `CLAUDE.md` | 平台开发硬规则 + 开发命令 |
| `README.md` | 对外首页（须与 VISION 一致） |

## 运行时

| 目录 | 状态 |
|------|------|
| `server/` | **SSOT** — 薄驱动 Engine + 看板服务端 + HTTP API + 中转站 + 知识库 + 配置化 + 部署模板 |
| `server/engine/` | 薄驱动核心（dispatch / main / scheduler / store / task / cluster） |
| `server/board/` | 看板服务端（loader / queries / export / models / scheduler） |
| `server/web/` | HTTP API + 静态页（server.py / brain.py 大脑 Agent 代理） |
| `server/config/` | 配置系统（env 加载器 + 执行体注册表，契约 §7） |
| `desktop/` | Desktop 壳源码（任意设备壳之一，构建产物 `.build/` 勿提交） |
| `docs/dispatch/` | ★ 任务卡文档（唯一事实源） |
| `.ccc/archive/legacy-retired-2026-08-02/` | 旧栈归档（scripts/ 等，已退役，勿引用） |

新增编排逻辑改 `server/`，不要平行第二条流水线。

# mx (medio-0) 开发技能指南

> 项目：medio-0 — 全栈媒体管理应用
> 技术栈：Rust (edition 2021) / axum 0.8 / SQLite (sqlx 0.8) / tokio 1 / React 19 + TypeScript 5.6 / Vite 6 / Tauri
> 仓库：/Users/fan/program/apps/medio-0（Mac2017）

## 常用命令

- 编译检查：`cargo check --workspace`
- 运行测试：`cargo test --workspace`
- 后端单测：`cargo test -p medio-core`
- 前端测试：`cd src/frontend && npx vitest run`
- 端到端测试：`python3 scripts/test_api_smoke.py`
- 构建：`cargo build --release`
- 代码检查：`cargo fmt --check && cargo clippy -- -D warnings`

## 关键模块

| Crate | 路径 | 职责 |
|-------|------|------|
| medio-core | src/backend/core/ | 核心逻辑、RSS 服务、数据库模型 |
| medio-server | src/backend/server/ | HTTP API 服务（axum） |
| medio-tauri | src/backend/tauri/ | Tauri 桌面壳 |

## 开发守则

1. 所有后端改动必须先 `cargo check` 通过再 commit
2. 修改数据库模型（sqlx）需同步更新迁移脚本
3. RSS 相关改动需确保 `test_rss.py` 通过
4. 前端改动需确保 `npx vitest run` 通过
5. 禁止引入新 crate 依赖（除非卡内明确允许）
6. API 签名变更需同步更新 `test_api_smoke.py`
7. 网络存储相关代码注意挂载抖动保护（历史教训：增量扫描误删）
# hp (知识库) 开发技能指南

> 项目：hp — 个人 AI agent 中央知识库基础设施
> 技术栈：Python / TypeScript / Bash / PostgreSQL 18.0 + pgvector / Ollama
> 仓库：/Users/fan/program/apps/hp（Mac2017）

## 常用命令

- 运行测试：`cd tests/server && pytest -v`
- KB 静态自检：`bash scripts/qa/verify-k23.sh`
- 短 chunk 门禁检查：`bash scripts/qa/verify-k23.sh`（目标 short_pct < 15%）
- KB 搜索验证：`python3 local/scripts/kb-search.py search "<query>"`
- 数据库操作：先建隧道 `/Users/fan/.ccc/bin/start-hp-db-tunnel.sh`，`source .env`

## 关键模块

| 模块 | 路径 | 职责 |
|------|------|------|
| memory-store | local/memory-store/ | 记忆存储服务 (:8082) |
| Dashboard API | local/ | 仪表盘 API (:8089) |
| collector | local/auto-collect/ | 多项目采集守护进程 |
| pipeline | local/pipeline/ | 知识入库管道 |

## 开发守则

1. 数据库操作前必须备份（`chunks_backup_<card>` / `documents_backup_<card>`）
2. 禁止在 M1 本地修改 hp 业务仓代码（必须通过 Desktop transfer → Engine）
3. 改动后运行 `verify-k23.sh` 确认 short_pct 未恶化
4. 采集器相关改动需监控稳定性（launchd plist）
5. 端口与路径以 qx-map `cluster/path-authority.md` 为准
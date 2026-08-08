# 2017 HP DB 访问环境（2026-08-08 固化）

## 背景
hp009 死循环根因：hp 业务仓在 Mac2017（`/Users/fan/program/apps/hp`），但 PG 在 HP 机器（`hp@hp` = 192.168.3.131，`/data/knowledge`，pg18:5432，documents=5058）。执行体在 2017 连 `127.0.0.1:5432`（2017 本地无 PG）→ Connection refused → 死循环。

## 已固化的环境（2017 侧）
1. **隧道脚本** `/Users/fan/.ccc/bin/start-hp-db-tunnel.sh`：建 SSH 隧道 `2017:5433 → hp:5432`（复用 ~/.ssh/config `Host hp`）。可复现，随需启动。
2. **hp 仓 .env** `/Users/fan/program/apps/hp/.env`：`KB_DB_HOST=127.0.0.1 KB_DB_PORT=5433 KB_DB_NAME=knowledge KB_DB_USER=knowledge KB_DB_PASS=...`。
3. **verify 脚本支持环境变量覆盖**：`scripts/qa/verify_project_id_mapping.py` DB 配置改读 KB_DB_*（默认保持 127.0.0.1:5432 兼容）。

## 使用方式
- hp 卡执行体：先跑 `/Users/fan/.ccc/bin/start-hp-db-tunnel.sh`，再 `source /Users/fan/program/apps/hp/.env` 后跑 hp 仓脚本。
- 验证命令：`cd /Users/fan/program/apps/hp && lsof -iTCP:5433 -sTCP:LISTEN || /Users/fan/.ccc/bin/start-hp-db-tunnel.sh; source .env && python3 scripts/qa/verify_project_id_mapping.py`（全过，5058 ✓）。

## 2017 Agent 基础环境（已核对/补齐）
| 项 | 状态 |
|----|------|
| OpenCode relay（loop/code :6102）| 已配 |
| Claude relay（:6100）| 已配 |
| OpenCode MCP（hp-kb/postgres/github/filesystem 等 9 个）| 已配 |
| Claude MCP（hp-kb/github/codebase-memory）| 本次补齐（~/.claude/.mcp.json）|
| Skills（ccc-protocol/code-review/codebase-memory 等）| 已装（~/.agents/skills）|

## 遗留
- hp009 产物（restore/verify/clean-chunks 7 commits）在 hp 仓 `codex/hp009-stock-short-chunk-and-rss-backfill` 分支，**未合入 hp 仓 main**（分叉，删了 local 组件 EmptyState.tsx，需人工确认后合并）。CCC 侧 hp009 卡已清理删除。
- 2017 Claude 未加 postgres MCP（hp-kb MCP + DB 直连已覆盖）。

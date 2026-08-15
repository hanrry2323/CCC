# 节点/路径域

> 来源：种子包 `01-nodes-paths.json`（qx-map `cluster/path-authority.md` + `docs/architecture.md` v0.70.0 + `ccc-relay-双轨决议-2026-08-02.md` + `ccc-refactor-M2-生产验证-2026-08-03.md`）
> 初始化：2026-08-02 · M4 刷新：2026-08-03 · 之后知识库独立维护在此标注变更

## 机器节点

| 机器 | IP | OS | RAM | SSH 用户 | 访问方式 |
|------|-----|-----|-----|---------|---------|
| M1（本机） | 192.168.3.140 | macOS 26.5.2 arm64 | 8GB | apple | 本地 shell |
| Mac2017 | 192.168.3.116 | macOS 13.7.8 x86_64 | 16GB | fan | `ssh fan@192.168.3.116`（密钥 `~/.ssh/id_ed25519_xianyu`） |
| HP | 192.168.3.131 | Ubuntu 25.10 | 11GB | hp | `ssh hp@192.168.3.131`（密钥 `~/.ssh/id_ed25519_hp`） |
| Windows | 192.168.3.252 | Windows | — | win | `ssh win@192.168.3.252`（密钥 `~/.ssh/id_ed25519`） |
| surface-pro | 192.168.3.195 | Windows Server | — | test | SSH 免密（2026-08-15 接入，qx-map/CCC 已 clone） |

## CCC 拓扑（2017 单端终态）

**总览**：2017 单端 :7788 = CCC 唯一服务端 + 大脑宿主 + 执行机。任意设备壳经 HTTP 直连 2017。

### 2017 :7788 端点

| 端点 | 说明 |
|------|------|
| `/conversation` | → `brain.py`（大脑 Agent，Claude Code CLI via 6100） |
| `/board/*` | → 看板视图（snapshot/states/recent/roadmap/summaries） |
| `/ops/summary` | → 运维聚合（节点/红灯/概览） |
| `/session` | → 账号密码换 token |
| `/config` | → 前端配置注入（不含敏感字段） |

### 2017 三服务（launchd 常驻）

- `com.ccc.web-server` → `server/web/server.py :7788`（HTTP API + 静态页）
- `com.ccc.engine` → `server/engine/main.py`（薄驱动主循环）
- `com.ccc.board-scheduler` → `server/board/scheduler.py`（只读巡检 + 导出）

### 鉴权

对话口账号密码 + 会话 token（沿用 7788 鉴权地基，多壳必须锁门）。

## 各机器服务

### M1（开发机 + Codex 驻场·开发期工作站·后期壳之一）
- Codex Desktop
- ai-loop-router :4100/:4102（loop-router，Codex 智能路由；双轨决议保留，不停用）
- ccc-relay-runtime :4000（CCC relay，与 loop-router 独立）
- postgres :5432
- 退役服务：ccc-chat-server :7777（T34 归档）、ccc-agent-sidecar :7788（T34 归档）

### Mac2017（重活节点·CCC 唯一服务端 + 大脑宿主 + 执行机·qb 本体所在）
- `com.ccc.web-server :7788`（HTTP API + 静态页，launchd 常驻）
- `com.ccc.engine`（薄驱动 Engine，launchd 常驻）
- `com.ccc.board-scheduler`（只读巡检 + 导出，launchd 常驻）
- `com.ccc.ai-loop-router :6100/:6102`（CCC 专用中转站，launchd 常驻；6100=Anthropic 出口，6102=Relay flash 出口）
- 退役服务：ollama :11434（2026-08-02 已移除）、qx-observer :7777、xianyu :8080、redis :6379（2026-08-13 清理后停用）

### HP（存储 + 知识库服务 + medio-server）
- mcp-server :8083（知识库 MCP 唯一入口）
- memory-store :8082
- postgres :5432
- ollama（4 models，not for prod embedding）
- medio-server

## 中转站（历史双轨 → 2026-08-06 冷冻收敛）

**历史决议**：`ccc-relay-双轨决议-2026-08-02.md`（2026-08-02 曾拍板 M1 中转站 4100/4102 不停用、双轨并行）。

**2026-08-06 已冷冻**（qx-map `cluster.json:13` / `AGENTS.md:123`）：M1 loop-router（4100/4102）不再运行，模型出口统一走 Mac2017 `6100`（Anthropic）/ `6102`（OpenAI）；M1 Codex 改官方 DeepSeek 直连。下表 M1 列为历史参考，状态已标冷冻。

| | M1 loop-router | Mac2017 CCC relay |
|--|---------------|-------------------|
| 代码仓 | `/Users/apple/program/ai-loop-router` | `ai-loop-router-ccc`（Mac2017 本地实例） |
| 端口 | 4100/4102 | 6100/6102 |
| 上游 | opencode/minimax/zhipu 直连 | Anthropic 出口（6100）/ Relay flash 出口（6102） |
| Codex 是否用 | 否（2026-08-06 起官方 DeepSeek 直连） | 否（仅 CCC 体系） |
| 使用方 | M1 侧 Codex/Claude Code/OpenCode 智能路由 | 仅 Mac2017 侧 Claude Code + OpenCode + Engine env |
| 模型档位 | （依上游） | 统一 flash |
| 职责 | M1 侧智能路由 | CCC 体系专用中转站 |
| 状态 | 冷冻（2026-08-06 起不运行，历史参考） | 常驻（launchd `com.ccc.ai-loop-router`） |

**退役 relay**：M1 :4000（ccc-relay-runtime）早已离线，与双轨决议无关。

## HP 知识库

| 服务 | 位置 | 端口 | 说明 |
|------|------|------|------|
| mcp-server | HP | 8083 | 知识库 MCP 唯一入口 |
| memory-store | HP | 8082 | 记忆存储 |
| 知识数据 | HP `/data/knowledge/` | — | 外脑权威知识在 HP，M1 仅索引 |

**注意**：CCC 自建知识库（`knowledge/`）独立运行后不再读写 HP（D2/D3 独立红线）。

## 已退役端口（权威清单）

| 端口 | 说明 |
|------|------|
| 7777 | 旧 ccc-chat-server（M1）/ qx-observer（Mac2017 仍运行）；CCC 体系内已退役，T34 归档 |
| 7775 | 旧 Board API（已退役，T34 归档） |
| 17777 | 旧 Hub 端口（已退役，T31 文档基线切新架构时清零） |
| 7778 | 旧 Cockpit（src-tauri 旧桌面壳，T34 归档到 `docs/archive/ccc-legacy-2026-08-02/tauri-desktop-legacy/`） |
| 7788 sidecar | 旧 ccc-agent-sidecar，已退役，T34 归档；7788 现由 2017 web-server 接管 |
| 11434 | Mac2017 ollama（2026-08-02 已移除） |
| 4000 | ccc-relay-runtime（早已离线） |

**纪律**：退役端口禁止在现行文档出现，仅历史归档区可保留。

## 路径幻觉检查规则

1. 本机路径：`ls -d` 当场验证，不存在则不写
2. 集群路径：`ssh <host> 'ls -d ...'` 当场验证
3. SMB 路径：确认 `/Volumes/fan` 挂载再引用；卸载时改用 ssh
4. 旧快照：cluster.json 等过 3 天以上先重验再信
5. 写任何项目文档前对照本表；本表没有的路径 = 先查证再落盘
6. 退役端口（7777/7775/17777/7778/4000/11434）禁止在现行文档出现，仅历史归档区可保留

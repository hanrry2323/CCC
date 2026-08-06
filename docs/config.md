# CCC 配置系统（现行）

> **权威拓扑**：[`deploy/topology.md`](deploy/topology.md) · INDEX §0。  
> Hub `:7777` / Board `:7775` / 旧 `ccc-board-server.py` 角色 plist **已退役**（下文不再当默认）。

## 现行生产（2017）

| 面 | 端口 / 入口 | 配置 |
|----|-------------|------|
| HTTP 看板 / API / 对话 | **7788** | `server/config/config.env` · launchd `com.ccc.web-server` |
| Anthropic / Claude Code | **6100** | 中继 |
| Relay flash/code | **6102** | 中继 |
| Engine | launchd `com.ccc.engine` | `server/config/executors.json`（生产实机） |
| 看板调度 | launchd `com.ccc.board-scheduler` | `server/board/scheduler.py` |

模板见 `server/config/config.env.example`、`server/config/executors.example.json`。  
免登录：`CCC_WEB_AUTH_REQUIRED=0`（局域网单用户）。

## 仓库内配置落点

| 路径 | 用途 |
|------|------|
| `server/config/config.env` | 端口、路径、上游（零硬编码 D10） |
| `server/config/executors.json` | 执行体注册表（2017 实机为准） |
| `docs/projects/registry.yaml` | 项目前缀 / taskable 唯一事实源 |
| `templates/` · `.ccc/` | 历史项目级覆盖（业务仓）；平台核以 server/config 为准 |

## 史（勿当现行）

旧文曾写 `BOARD_PORT=7775`、Hub UI `7777`、`install-ccc-roles.sh` 七角色 interval、`AGENT_PLANNER_BASE_URL :4100`。  
那些属于 Hub 时期；冲突时以 topology + `server/config/` 为准。

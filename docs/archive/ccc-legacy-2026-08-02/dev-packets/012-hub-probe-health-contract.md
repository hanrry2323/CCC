# DEV-PACKET: hub-probe-health-contract

> **状态（2026-07-28）**：Cursor 已直接落地（非 Claude 草稿）。本文件保留为口径 SSOT 与回归说明。  
> 合入权威 = Cursor。**禁止**新造 Hub `GET /api/health` 产品路由。

## 1. 总目标

统一 Hub / sidecar 探活口径，消除「404/401 = 系统挂了」假红。

## 2. 契约（硬）

| 探针 | 期望 | 含义 |
|------|------|------|
| `GET {Hub}/api/health` | **404** | Hub **无**此路由；404=预期，不是宕机 |
| `GET {Hub}/api/desktop/projects` 无 auth | **401** | Hub Basic Auth 开着（默认） |
| `GET {Hub}/api/desktop/projects` + `-u ccc:ccc` | **200** | **唯一推荐** Hub 可达性探针（或 `/api/desktop/version`） |
| `GET {sidecar}/health` | **200** | 对话口；默认 **无** Agent Token（`CCC_AGENT_AUTH=0`） |

Hub = `http://127.0.0.1:17777`（M1 隧道）或 `http://127.0.0.1:7777`（2017 本机）。  
sidecar = `http://127.0.0.1:7788`。

鉴权差异是**设计**（编排 API 有账密；对话口默认内网免 Token），不是故障。

## 3. 已落地路径

- [`scripts/ccc-hub-probe.sh`](../scripts/ccc-hub-probe.sh) — 一键契约验收  
- [`docs/ccc-hub-ports.md`](../ccc-hub-ports.md) — 探活专节  
- [`docs/product/hub-api-v1.md`](../product/hub-api-v1.md) — 探测节补强  
- fleet / dual-host / smoke 本已用 `desktop/projects`（勿改回 `/api/health`）

## 4. 验收

```bash
bash scripts/ccc-hub-probe.sh
# OVERALL pass
```

## 5. 黑名单

- 在 Hub 新增 `/api/health`「假绿」路由  
- 改 `~/.ccc/**` 密钥 / plist  
- Ops UI 抛光

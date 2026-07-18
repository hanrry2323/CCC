# Desktop 连接契约（工程 SSOT）

> 产品架构见 [`ccc-desktop-architecture.md`](ccc-desktop-architecture.md)。  
> 本文只约束 Client↔Hub 连接行为，不改产品语义。

## 硬规则

| # | 规则 |
|---|------|
| 1 | 全 App **最多 1 条 chat SSE** + **1 条 flow SSE**（分属独立 `URLSession`） |
| 2 | 切会话 **不得** 拆掉 / 重建 flow SSE；仅换项目时 `ensureFlowSSE` 重建 |
| 3 | 发送 / 取消对话 **不得** `cancel` flow 任务 |
| 4 | `connected` **只**由 projects / 健康探测更新；单条 chat 失败 →「本条失败」 |
| 5 | chat SSE 必须收到 `done` 且 `partial != true` 才算成功；否则「回复中断」 |
| 6 | 短请求经 `HubRequestGate`（含 transfer）；防止打满单进程 Hub |

## 方案 Agent

运行时由 Hub 决定：`CCC_EXECUTOR=loop-code` → `vendor/loop-code/cli`。  
探测：`GET /api/desktop/config` → `agent_runtime` / `agent_cli`。

## 验收

```bash
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-agent.sh
CCC_SERVER=http://192.168.3.116:7777 bash desktop/scripts/smoke-ui-chat.sh
```

# Desktop 连接契约（工程 SSOT）

> 产品架构见 [`ccc-desktop-architecture.md`](ccc-desktop-architecture.md)。  
> 本文只约束 Client↔Hub 连接行为，不改产品语义。

## 硬规则

| # | 规则 |
|---|------|
| 1 | **chat SSE** 与 **flow SSE** 分属独立 `URLSession`（不得共池抢连接） |
| 1a | 本机 Agent：最多 **3 路** chat 并行；Hub 回退：全 App **1 路** chat |
| 1b | flow SSE：全 App **1 条**；切会话不重建 |
| 2 | 切会话 **不得** 拆掉 / 重建 flow SSE；仅换项目时 `ensureFlowSSE` 重建 |
| 3 | 发送 / 取消对话 **不得** `cancel` flow 任务 |
| 4 | `connected` **只**由 projects / 健康探测更新；单条 chat 失败 →「本条失败」 |
| 5 | chat SSE 必须收到 `done` 且 `partial != true` 才算成功；否则「回复中断」 |
| 6 | 短请求经 `HubRequestGate`（含 transfer）；防止打满单进程 Hub |

## 方案 Agent

**热路径（目标）**：本机 Agent Sidecar（`127.0.0.1:7788`）→ `vendor/loop-code/cli` → Router。  
Desktop 探测 `GET {CCC_AGENT}/health`；可用则 `POST` 本地 `/api/chat`（无 Basic auth）。  
聊完 `PUT Hub /api/desktop/threads/{id}/messages` 落盘；转任务 / 右栏 flow 仍走 Hub。

**回退**：sidecar 不可用 → Hub `/api/chat`；发送前可 `POST /api/desktop/agent/warm` 预热槽位。

Hub 侧探测：`GET /api/desktop/config` → `agent_runtime` / `agent_cli`。  
详见 [`desktop-agent-sidecar.md`](desktop-agent-sidecar.md)。

## 验收

```bash
bash scripts/ccc-agent-sidecar.sh   # 本机常驻
bash scripts/spike-loopcode-ttfb.sh # Hub vs 本机 TTFB
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-agent.sh
```

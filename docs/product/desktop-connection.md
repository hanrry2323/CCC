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
| 5a | 同会话 chat 失败可自动重试 **1** 次（保留本地消息；半截助手清空再流） |
| 5b | 聊天流式**不**暂停 flow snapshot；仅 `syncThreadFromServer` 在生成中跳过覆盖 messages |
| 6 | 短请求经 `HubRequestGate`（含 transfer）；防止打满单进程 Hub |

## 方案 Agent

**热路径**：本机 Agent Sidecar（`127.0.0.1:7788`）→ `vendor/loop-code/cli` → Router。  
Desktop `ensureLocalAgent`：探测（30s 缓存）→ 失败则自启 sidecar → 再探测；可用则 `POST` 本地 `/api/chat`。  
聊完 `PUT Hub /api/desktop/threads/{id}/messages`（含 `tool_steps`）；转任务 / 右栏仍走 Hub。

**回退**：自启仍失败 → 状态栏 **Hub 回退** + toast；`POST /api/desktop/agent/warm`。  
**工作区**：`localWorkspaceMap[projectId]` → 全局 fallback → Hub path 若本机存在。

详见 [`desktop-agent-sidecar.md`](desktop-agent-sidecar.md)。

## ~95% 验收清单

1. 杀 sidecar → 开 App → 自动起来且徽章「本机 Agent」
2. 带工具一轮 → 重开 App → 同会话仍见 tool 芯片
3. 两会话并行生成（sidecar）不互抢
4. 业务项目绑本机路径后 `project_path` 正确
5. sidecar 故意失败 → 明示 Hub 回退
6. 助手输出 `ccc-transfer` → 出现「确认转任务」条，少手填过门禁
7. 转任务后 ≤15s 右栏可见 epic→works 生长动画（或白话「Engine 未扇出」）

```bash
bash scripts/spike-loopcode-ttfb.sh
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-agent.sh
bash scripts/smoke-desktop-stable.sh
python3 scripts/tests/test_ccc_transfer_samples.py
```

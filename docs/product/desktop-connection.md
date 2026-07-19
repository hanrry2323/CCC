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
| 4 | `connected` = **本机 Agent 健康或 Hub projects OK**；Hub 抖仍可聊；单条 chat 失败 →「本条失败」 |
| 4a | **本机会话 SSOT**：`~/Library/Application Support/CCCDesktop/sessions/`；Hub `PUT` 异步镜像 + 失败重试 |
| 5 | chat SSE 必须收到 `done` 且 `partial != true` 才算成功；否则「回复中断」 |
| 5a | 同会话 chat 失败可自动重试 **1** 次（保留本地消息；半截助手清空再流） |
| 5b | 聊天流式**不**暂停 flow snapshot；仅 `syncThreadFromServer` 在生成中跳过覆盖 messages |
| 5c | 短问 `prompt_mode=light`；含「定稿/转任务/下达」或 &gt;80 字 → `full` |
| 6 | 短请求经 `HubRequestGate`（含 transfer）；防止打满单进程 Hub |

## 方案 Agent

**热路径**：本机 Agent Sidecar（`127.0.0.1:7788`，**launchd `com.ccc.agent-sidecar` KeepAlive**）→ `vendor/loop-code/cli` → Router。  
Desktop `ensureLocalAgent`：探测 → `launchctl kickstart` / `install-agent-sidecar-plist.sh` → `POST /warm`；每 240s keep-warm。  
消息先写本机盘，再 `PUT Hub`（失败入 `pending-sync.json`）。转任务 / 右栏仍要求 Hub。

**回退**：sidecar 失败 → **Hub 回退**；Hub 失败但 sidecar 活 → **本机 Agent · Hub 暂不可达**（可聊，不受 LAN 抖影响）。  
**工作区**：`localWorkspaceMap[projectId]` → 全局 fallback → Hub path 若本机存在。

详见 [`desktop-agent-sidecar.md`](desktop-agent-sidecar.md)。

## Cursor 感性能验收

| 指标 | 目标 |
|------|------|
| 热进程短问首 token | ≤1s（`spike-loopcode-ttfb.sh` + `/warm`） |
| 切会话 / 重开 App | ≤100ms 出本机缓存（含 tool_steps） |
| Hub 断 10s | 仍可聊；状态非「未连接」 |

```bash
bash scripts/spike-loopcode-ttfb.sh
bash scripts/smoke-desktop-stable.sh
python3 scripts/tests/test_hub_voice.py
```

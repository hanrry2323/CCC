# Desktop 连接契约（工程 SSOT）

> 产品架构见 [`ccc-desktop-architecture.md`](ccc-desktop-architecture.md)。  
> **对话/编排边界基线**：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> 本文约束 Client 连接行为：聊天走本机 sidecar；Hub 只承载信息流（transfer / flow / 可选镜像）。  
> **架构对齐（2026-07-19）**：Desktop+loop-code = M1 对话意图工具；Mac2017 = 纯编排消费；Hub `/api/chat` 已删，无回退路径。

## 硬规则

| # | 规则 |
|---|------|
| 1 | **chat SSE** 与 **flow SSE** 分属独立 `URLSession`（不得共池抢连接） |
| 1a | 本机 Agent：最多 **3 路** chat 并行；**无 Hub chat 回退**（Hub `/api/chat` 已删） |
| 1b | flow SSE：全 App **1 条**；切会话不重建 |
| 2 | 切会话 **不得** 拆掉 / 重建 flow SSE；仅换项目时 `ensureFlowSSE` 重建 |
| 3 | 发送 / 取消对话 **不得** `cancel` flow 任务 |
| 4 | `connected`（可聊）= **本机 Agent 健康**；Hub 仅影响转任务/右栏；单条 chat 失败 →「本条失败」 |
| 4a | **本机会话 SSOT**：`~/Library/Application Support/CCCDesktop/sessions/`；Hub `PUT` 为可选镜像，非对话权威 |
| 4b | **常态禁止** 对话打 Hub `/api/chat`（路由已删，404）；对话只走本机 sidecar |
| 5 | chat SSE 必须收到 `done` 且 `partial != true` 才算成功；否则「回复中断」 |
| 5a | 同会话 chat 失败可自动重试 **1** 次（保留本地消息；半截助手清空再流）；**排除** 401/403/503 鉴权与路径拒绝 |
| 5a1 | 取消生成：Desktop **总是** `session/drop` 回收 live slot，**保留** `claude_session_id`；重置/归档才清 resume |
| 5a2 | 失败可见：状态栏「本条失败 · 短因」+ 重试/清槽；账本 `~/Library/Logs/CCC/desktop-chat-turns.jsonl` |
| 5b | 聊天流式**不**暂停 flow snapshot；仅 `syncThreadFromServer` 在生成中跳过覆盖 messages |
| 5c | 短问 `prompt_mode=light`；含「定稿/转任务/下达」或 &gt;80 字 → `full` |
| 6 | 短请求经 `HubRequestGate`（含 transfer）；防止打满单进程 Hub |

## 方案 Agent

**热路径**：本机 Agent Sidecar（`127.0.0.1:7788`，**launchd `com.ccc.agent-sidecar` KeepAlive**）→ `vendor/loop-code/cli` → **MiniMax Anthropic 直连**（`MiniMax-M3`）。  
OpenCode（Engine 写码）：**讯飞直连** `xfyun/code`（`~/.config/opencode/opencode.json`）；智谱 `zhipu/flash` 备用。  
~~经 2017 `:4000/:4002` 中转已退役。~~  
Desktop `ensureLocalAgent`：探测 → `launchctl kickstart` / `install-agent-sidecar-plist.sh` → `POST /warm`；每 240s keep-warm。  
消息先写本机盘，再 `PUT Hub`（失败入 `pending-sync.json`）。转任务 / 右栏仍要求 Hub。

**未就绪处理**：sidecar 起不来 → 状态「本机 Agent 未就绪」+ toast；**不回退 Hub**（Hub `/api/chat` 已删）。后台每 3s 重探，sidecar 恢复后自动转「本机 Agent」。  
**Hub 抖动**：Hub 不可达但 sidecar 活 → 仍可聊，状态「Hub 暂不可达（可聊）」，仅转任务/右栏受影响。  
**工作区**：业务仓 **无本机第二树**；对话事实以 Hub baseline（2017）为准。`localWorkspaceMap` 仅可选映射平台仓 `ccc` → 本机 CCC；禁止映射业务仓 / archive。
详见 [`desktop-agent-sidecar.md`](desktop-agent-sidecar.md)。

## Hub 自动恢复 SLA（F1）

> Brief：[`docs/briefs/2026-07-21-f1-disconnect-recovery.md`](../briefs/2026-07-21-f1-disconnect-recovery.md)。  
> 对称于 sidecar `startAgentRecoverLoop`：Hub 不可达时启动轻量探活，恢复后自动收口，用户不必只靠点「重试」。

| 项 | 规格 |
|----|------|
| 探活间隔 | **3–5s**（实现取 4s）；成功即停；经 `HubRequestGate`，勿打爆 |
| 探活成功后序 | `hubReachable=true` → `flushPendingHubSync` → `flushTransferOutbox` → 当前项目 `bindFlowToCurrentThread`（snapshot 兜底 + SSE 对齐） |
| Hub 断 ≥10s + sidecar 健康 | 仍可聊；状态栏 **「本机 Agent · Hub 暂不可达（可聊）」**；禁止全局「未连接」误报 |
| 转任务（Hub 断） | 入 `transfer-outbox.json`；投递态 `queued`（待投递）；toast「Hub 暂不可达，已排队待投递」 |
| 恢复且 flush ≥1 笔 | toast **「Hub 已恢复 · 排队任务已投递」**；投递态 → `delivered` / `accepted`（既有 `applyTransferSuccess`） |
| 恢复且 outbox 空 | 仅更新状态栏（避免吵）；不强制 toast |
| 手动「重试 / 重新连接」 | 与自动探活 **幂等**（不双投；依赖 `client_request_id`） |
| 右栏 | 恢复后 snapshot 与 `boundEpicId` 一致，不串他 epic |

## Cursor 感性能验收

| 指标 | 目标 |
|------|------|
| 热进程短问首 token | ≤1s（`spike-loopcode-ttfb.sh` + `/warm`） |
| 切会话 / 重开 App | ≤100ms 出本机缓存（含 tool_steps） |
| Hub 断 10s | 仍可聊；状态非「未连接」 |
| Hub 恢复后自动探活 | ≤5s 内检测到（探活周期上限） |
| 恢复后 outbox | 无需用户再点一次即可 flush |

```bash
bash scripts/spike-loopcode-ttfb.sh
bash scripts/smoke-desktop-stable.sh
bash scripts/smoke-hub-outage-outbox.sh
python3 scripts/tests/test_hub_voice.py
```

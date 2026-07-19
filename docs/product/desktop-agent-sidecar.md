# Desktop 本机 Agent Sidecar

> 目标：方案 Agent 热路径在本机（launchd + loop-code）；**编排面在中心机**。  
> 边界基线：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> Hub 只承载 **信息流**（transfer / flow / 可选会话镜像），不是主聊天。

## 链路

```text
Desktop bootstrap → ensureLocalAgent (probe / auto-start)
Desktop UI ←localhost SSE→ ccc-agent-sidecar (:7788)
                              → ClaudeSDKClient → vendor/loop-code/cli
                              → ANTHROPIC_BASE_URL
Desktop UI ──PUT messages(+tool_steps)备份 / transfer / flow──→ Hub (:7777)
```

**模型出口默认**：`install-agent-sidecar-plist.sh` 写 `ANTHROPIC_BASE_URL=http://192.168.3.116:4000`（Mac2017 中转）。覆盖：仅环境变量 `CCC_AGENT_ROUTER`（不继承 shell 的 `ANTHROPIC_BASE_URL`）。

## 启动（launchd 常驻）

- **日常**：`bash scripts/install-agent-sidecar-plist.sh --start`（或打开 Desktop，自动 install/kickstart）。
- **KeepAlive**：崩溃 / 误杀后 launchd 自动拉起；**不依赖 nohup**，与 Hub 控制面无关。
- **手工前台调试**：

```bash
bash scripts/ccc-agent-sidecar.sh          # 前台
bash scripts/ccc-agent-sidecar.sh status
bash scripts/ccc-agent-sidecar.sh stop
# CCC_AGENT_PORT=7788 ANTHROPIC_BASE_URL=http://192.168.3.116:4000
```

健康检查：`curl -s http://127.0.0.1:7788/health`（`router` 应含 `192.168.3.116:4000`）  
日志：`~/Library/Logs/CCC/agent-sidecar.log` / `.err`  
plist：`~/Library/LaunchAgents/com.ccc.agent-sidecar.plist`

## Desktop 行为

| 设置 | 默认 | 作用 |
|------|------|------|
| `ccc.agent` / `CCC_AGENT` | `http://127.0.0.1:7788` | 探测成功则聊天打本地 |
| `ccc.home` / `CCC_HOME` | 自动探测 | 拉起 sidecar 的 CCC 仓根 |
| `ccc.localWorkspaceMap` | `{}` | `projectId → 本机路径` |
| `ccc.localWorkspace` | 空 | 全局 fallback cwd |

状态栏徽章：**本机 Agent** / **本机 Agent 未就绪**（**禁止** Hub `/api/chat` 回退）。可聊 ≠ 可转任务。  
探测成功缓存 30s。App 退出不杀 sidecar（保暖）。

消息落盘含 `tool_steps` / `files_changed` / `tools_finished`。

## Hub API（编排侧）

| 方法 | 路径 | 用途 |
|------|------|------|
| `PUT` | `/api/desktop/threads/{id}/messages` | 会话**备份**（非权威；Engine 不读） |
| `POST` | `/api/desktop/agent/warm` | Hub 槽位预热（网页/运维；Desktop 对话不依赖） |
| `POST` | `/api/desktop/transfer` | 转任务（过桥信息流） |
| SSE | `/api/desktop/flow/...` | 右栏扇出状态 |

### Sidecar 本机 API

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/health` | 存活 |
| `POST` | `/warm` | keep-warm（cli/router 探测） |
| `POST` | `/api/chat` | SSE 对话（`prompt_mode`: `light`\|`full`） |

Desktop 本机会话目录：`~/Library/Application Support/CCCDesktop/sessions/`。

## 约束

1. **arch**：M1 用 arm64 `vendor/loop-code/cli`；**Mac2017 不再部署 loop-code**（架构对齐 2026-07-19；Hub `/api/chat` 已删）。
2. **工作区**：聊天 cwd 本机；Engine 在 Server — 转任务只带意图。
3. **安全**：sidecar 只绑 `127.0.0.1`。
4. **编排仓**可聊；仅转任务禁用。

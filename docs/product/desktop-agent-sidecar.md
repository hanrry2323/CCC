# Desktop 本机 Agent Sidecar

> 目标：方案 Agent 热路径接近本机 Claude（常驻 loop-code），Hub 只管落盘 / 转任务 / 右栏编排。  
> **Desktop 负责拉起 sidecar**（探测失败则 `nohup` 启 `scripts/ccc-agent-sidecar.sh`）。

## 链路

```text
Desktop bootstrap → ensureLocalAgent (probe / auto-start)
Desktop UI ←localhost SSE→ ccc-agent-sidecar (:7788)
                              → ClaudeSDKClient → vendor/loop-code/cli
                              → ANTHROPIC_BASE_URL
Desktop UI ──PUT messages(+tool_steps) / transfer / flow──→ Hub (:7777)
```

## 启动

- **日常**：打开 CCC Desktop 即可；health 失败时自动拉起。
- **手工**：

```bash
bash scripts/ccc-agent-sidecar.sh
# CCC_AGENT_PORT=7788 CCC_AGENT_CWD=<本机业务仓>
# ANTHROPIC_BASE_URL=http://192.168.3.116:4000
```

健康检查：`curl -s http://127.0.0.1:7788/health`  
日志：`~/Library/Logs/CCC/agent-sidecar.log`

## Desktop 行为

| 设置 | 默认 | 作用 |
|------|------|------|
| `ccc.agent` / `CCC_AGENT` | `http://127.0.0.1:7788` | 探测成功则聊天打本地 |
| `ccc.home` / `CCC_HOME` | 自动探测 | 拉起 sidecar 的 CCC 仓根 |
| `ccc.localWorkspaceMap` | `{}` | `projectId → 本机路径` |
| `ccc.localWorkspace` | 空 | 全局 fallback cwd |

状态栏固定徽章：**本机 Agent** / **Hub 回退**（失败 toast 明示，不静默迷路）。  
探测成功缓存 30s。App 退出不杀 sidecar（保暖）。

消息落盘含 `tool_steps` / `files_changed` / `tools_finished`。

## Hub API（编排侧）

| 方法 | 路径 | 用途 |
|------|------|------|
| `PUT` | `/api/desktop/threads/{id}/messages` | Hub 异步镜像（含 tool_steps） |
| `POST` | `/api/desktop/agent/warm` | Hub 槽位预热（回退路径） |
| `POST` | `/api/desktop/transfer` | 转任务 |
| SSE | `/api/desktop/flow/...` | 右栏 |

### Sidecar 本机 API

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/health` | 存活 |
| `POST` | `/warm` | keep-warm（cli/router 探测） |
| `POST` | `/api/chat` | SSE 对话（`prompt_mode`: `light`\|`full`） |

Desktop 本机会话目录：`~/Library/Application Support/CCCDesktop/sessions/`。

## 约束

1. **arch**：本机 M 系列用 arm64 `vendor/loop-code/cli`；2017 Hub 用 x86_64。
2. **工作区**：聊天 cwd 本机；Engine 在 Server — 转任务只带意图。
3. **安全**：sidecar 只绑 `127.0.0.1`。
4. **编排仓**可聊；仅转任务禁用。

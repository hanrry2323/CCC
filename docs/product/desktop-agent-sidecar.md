# Desktop 本机 Agent Sidecar

> 目标：方案 Agent 热路径接近本机 Claude（常驻 loop-code），Hub 只管落盘 / 转任务 / 右栏编排。

## 链路

```text
Desktop UI ←localhost SSE→ ccc-agent-sidecar (:7788)
                              → ClaudeSDKClient → vendor/loop-code/cli
                              → ANTHROPIC_BASE_URL (默认 2017:4000)
Desktop UI ──sync/transfer/flow──→ Hub (:7777) → Board / Engine
```

## 启动

```bash
# 依赖：.venv-hub + arch 匹配的 vendor/loop-code/cli
bash scripts/ccc-agent-sidecar.sh
# 环境变量：CCC_AGENT_PORT=7788 CCC_AGENT_CWD=<本机业务仓>
#          ANTHROPIC_BASE_URL=http://192.168.3.116:4000
```

健康检查：`curl -s http://127.0.0.1:7788/health`

## Desktop 行为

| 设置 | 默认 | 作用 |
|------|------|------|
| `ccc.agent` / `CCC_AGENT` | `http://127.0.0.1:7788` | 探测成功则聊天打本地 |
| `ccc.localWorkspace` | 空 | sidecar `project_path`；空则 sidecar 默认 CCC 仓根 |

状态栏显示「本机 Agent」+ `loop-code` 徽标。sidecar 挂掉时自动回退 Hub，并在发送前 `POST /api/desktop/agent/warm`。

## Hub API（编排侧）

| 方法 | 路径 | 用途 |
|------|------|------|
| `PUT` | `/api/desktop/threads/{id}/messages` | 本地聊完落盘 |
| `POST` | `/api/desktop/agent/warm` | Hub 槽位预热（过渡） |
| `POST` | `/api/desktop/transfer` | 转任务（不变） |
| SSE | `/api/desktop/flow/...` | 右栏（不变） |

## Spike

```bash
bash scripts/spike-loopcode-ttfb.sh
```

对比 Hub 与 local-agent 的 `time_starttransfer`（TTFB）。

## 约束

1. **arch**：本机 M 系列用 arm64 `vendor/loop-code/cli`；2017 Hub 用 x86_64。
2. **工作区双路径**：聊天 cwd 在本机；Engine 在 Server 仓 — 转任务只带意图/epic，执行仍在 Server。
3. **安全**：sidecar 只绑 `127.0.0.1`，勿对局域网裸开。
4. **编排仓**：`role=orch`（CCC）**可以对话**；仅「转任务 / engine 下达」禁用。有业务仓时 Desktop 默认选可下达项目。

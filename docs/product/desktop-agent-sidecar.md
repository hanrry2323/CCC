# Desktop 本机 Agent Sidecar

> 目标：方案 Agent 热路径在本机（launchd + loop-code）；**编排面在中心机**。  
> 边界基线：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> Hub 只承载 **信息流**（transfer / flow / 可选会话镜像），不是主聊天。  
> 热路径防挂死（2026-07-19 / `13ec205`）：锁超时、真暖、禁乱杀、ping→连接中。

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

- **日常**：`bash scripts/install-agent-sidecar-plist.sh --start`（或打开 Desktop，自动 install）。
- **KeepAlive**：崩溃 / 误杀后 launchd 自动拉起；**不依赖 nohup**，与 Hub 控制面无关。
- **Desktop `ensureRunning`**：先 `GET /health`；**健康则直接返回，禁止 `kickstart -k`**。仅 health 失败时 soft kickstart，仍失败才 `-k`。
- **手工前台调试**：

```bash
bash scripts/ccc-agent-sidecar.sh          # 前台
bash scripts/ccc-agent-sidecar.sh status
bash scripts/ccc-agent-sidecar.sh stop
# CCC_AGENT_PORT=7788 ANTHROPIC_BASE_URL=http://192.168.3.116:4000
```

健康检查：`curl -s http://127.0.0.1:7788/health`  
若日志出现 `Too many open files`：`bash scripts/install-agent-sidecar-plist.sh --start`（plist 已抬高 FD 上限）后重开 Desktop。  
日志：`~/Library/Logs/CCC/agent-sidecar.log` / `.err`  
plist：`~/Library/LaunchAgents/com.ccc.agent-sidecar.plist`


## 热路径可靠性（slot / warm / UX）

| 机制 | 默认 | 说明 |
|------|------|------|
| `CHAT_LOCK_WAIT` | 15s | 等不到 `slot.lock` → SSE `lock_timeout` + force-drop |
| `CHAT_CONNECT_TIMEOUT` | 30s | `_ensure_connected` 硬上限 |
| `CHAT_DRAIN_TIMEOUT` | 8s | 超时后有界 drain；禁止无限占锁 |
| `CHAT_WARM_LOCK_WAIT` | 3s | warm 抢锁失败快返回，不堵 chat |
| `CHAT_FIRST_EVENT_TIMEOUT` | 45s | query 后无任何可映射事件（delta/tool/…）→ `first_event_timeout` + 回收 slot |
| `CHAT_TOOL_STALL_TIMEOUT` | 60s | 已见 `tool_use` 但无 `tool_result` → `tool_stall` + 回收 |
| SSE `ping` | connect 前 + idle 15s | **有心跳 ≠ 有进展**；ping 可带 `awaiting` / `stall_in_s`；Desktop **不得**用 ping 重置进展时钟 |
| slot 回收 | 超时/异常 | disconnect + 杀掉本 slot 记下的 `loop-code/cli` PID，防僵尸占坑 |
| discuss 工具 | 含 WebFetch/WebSearch | 靠超时回收 + `DISCUSS_TOOL_DISCIPLINE`，**不靠删能力止血** |
| 真暖 | `POST /warm` + `slot.connected` | 无 `project_path` 的 cli-only warm **不算**已暖 |
| warm `tool_mode` | 与本条 chat 一致 | 避免 discuss / engineer 双 slot 冷启 |
| chat body | 优先 `prompt` | 有 prompt 时 Desktop 发空 `messages[]` |

环境变量前缀：`CCC_CHAT_*`（见 `scripts/chat_server/config.py`）。

**体感验收**：进项目能出字或在 ≤45s 内看到明确错误（非无限转圈）；工具执行时状态栏显示工具名；打断/超时后同项目下一条可发；health 正常时反复打开 App **无**新的 exit 143 风暴；右栏「编排空闲·等定稿下达」≠ 对话故障。

## Desktop 行为

| 设置 | 默认 | 作用 |
|------|------|------|
| `ccc.agent` / `CCC_AGENT` | `http://127.0.0.1:7788` | 探测成功则聊天打本地 |
| `ccc.home` / `CCC_HOME` | 自动探测 | 拉起 sidecar 的 CCC 仓根 |
| `ccc.localWorkspaceMap` | `{}` | `projectId → 本机路径` |
| `ccc.localWorkspace` | 空 | 全局 fallback cwd |

**业务仓迁到 2017 / 注册 / 在 Desktop 开项目对话**：  
[`../runbooks/app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md) · Agent 交接：[`desktop-agent-handoff.md`](desktop-agent-handoff.md)。

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
| `POST` | `/warm` | keep-warm：**带 `project_path` 才预连 SDK slot**；响应含 `slot.connected` |
| `POST` | `/api/chat` | SSE 对话（`prompt_mode`: `light`\|`full`；`tool_mode`: `discuss`\|`engineer`，默认 `discuss` 无 Write/Edit/Bash） |
| `POST` | `/api/session/drop` | 重置对话：丢 live slot |

Desktop 本机会话目录：`~/Library/Application Support/CCCDesktop/sessions/`。

## 多端版本对齐

对话热路径代码在 **M1**（Desktop 二进制 + sidecar 进程读本机仓）。编排 API 在 **Mac2017**（Hub）。两边 CCC 仓应同 commit。

```bash
# M1
cd ~/program/CCC && git rev-parse --short HEAD
curl -s http://127.0.0.1:7788/health
# 装 Desktop：bash desktop/scripts/package-baseline.sh && cp -R desktop/.build/CCCDesktop.app /Applications/
# 热更 sidecar：launchctl kickstart -k "gui/$(id -u)/com.ccc.agent-sidecar"

# Mac2017（SSH host mac2017）
cd ~/program/CCC && git pull --ff-only origin main && git rev-parse --short HEAD
launchctl kickstart -k "gui/$(id -u)/com.ccc.chat-server"
curl -s -u ccc:ccc http://127.0.0.1:7777/api/ops/router-usage
```

打包/安装细节：[`../deploy/desktop.md`](../deploy/desktop.md)。

## 约束

1. **arch**：M1 用 arm64 `vendor/loop-code/cli`；**Mac2017 不再部署 loop-code**（架构对齐 2026-07-19；Hub `/api/chat` 已删）。
2. **工作区**：聊天 cwd 本机；Engine 在 Server — 转任务只带意图。
3. **热路径**：见上文「热路径可靠性」——锁超时 force-drop、真暖、禁乱杀、ping 可见。
4. **安全**：sidecar 只绑 `127.0.0.1`。
5. **编排仓**可聊；仅转任务禁用。
6. **一项目一会话**：`{project_id}::main`；隔离靠 session/cwd/board，不是每项目独立进程。

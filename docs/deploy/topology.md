# CCC 部署拓扑 — Server / Client

> SSOT：服务端与客户端职责。更新日期：2026-07-21（开发通道 / Desktop 默认 MiniMax）。  
> 相关：[`server-layout.md`](server-layout.md) · [`desktop.md`](desktop.md) · [`../product/dev-channel.md`](../product/dev-channel.md) · [`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md) · [`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)

---

## 一句话

**M1 = 对话脑（Desktop + loop-code）；Mac2017 = 编排手（Hub + Board + Engine + 业务仓）。**  
中间只交结构化信息流（transfer / flow）。  
**模型出口直连上游**：Claude / loop-code → MiniMax；OpenCode → 讯飞。~~ai-loop-router `:4000/:4002` 已退役~~。

---

## 角色

| 角色 | 机器 | IP | 职责 |
|------|------|-----|------|
| **Client（对话）** | M1 | `192.168.3.140` | **CCC Desktop + sidecar `:7788` + arm64 loop-code**；本机会话 SSOT；远程浏览器聊亦打此口 |
| **Server（编排）** | Mac2017 | `192.168.3.116` | Hub API、Board、Engine（Claude 扇出）、OpenCode（dev 写码）、业务工作区、上游 API key |
| **Client（运维）** | 浏览器 | — | 网页 Hub `:7777`（看板/运维）；**不是**对话入口 |

同一时刻：**只一台 Engine**（Server）。  
**M1 不跑 Engine、不扇出 work、不在业务仓写码**（边界基线）。

---

## 模型出口（直连）

| 工具 | 机器 | 上游 | 配置 |
|------|------|------|------|
| loop-code（Desktop 对话） | M1 sidecar | **MiniMax** Anthropic（**默认 / 现网**） | `ANTHROPIC_BASE_URL=…`；**配置家** `CLAUDE_CONFIG_DIR=~/.ccc/loop-code`；见 [`../product/loop-code-ownership-cut.md`](../product/loop-code-ownership-cut.md) |
| Claude（product / reviewer） | Mac2017 Engine | **MiniMax** | 同上 key；**配置家** `CLAUDE_CONFIG_DIR=~/.ccc/engine-claude`（仍用 x86 原版 CLI，不换 loop-code） |
| OpenCode（dev 写码） | Mac2017 | **讯飞** `xfyun/code` | `~/.config/opencode/opencode.json`；备用 `zhipu/flash` |

`infra/ai-loop-router` 仅归档参考；launchd `com.ai-loop-router` **已停用**（plist 移至 `~/Library/LaunchAgents/disabled-relay-*`）。

---

## 端口

### M1（对话面）

| 端口 | 服务 | 说明 |
|------|------|------|
| **7788** | CCC Agent Sidecar | Desktop **与远程浏览器**对话热路径；launchd `com.ccc.agent-sidecar` KeepAlive |
| **17777** | Hub SSH 隧道（本机） | `com.ccc.hub-tunnel`：`ssh -L` → 2017 `:7777`；**Desktop/sidecar 默认 Hub URL** |

Sidecar 出口：MiniMax 直连（见上表）。  
Hub 传输：[`../product/hub-ssh-tunnel.md`](../product/hub-ssh-tunnel.md) · 热路径：[`../product/desktop-agent-sidecar.md`](../product/desktop-agent-sidecar.md) · [`desktop.md`](desktop.md) · 双口：[`../product/hub-remote-management.md`](../product/hub-remote-management.md)。

### Mac2017（编排面）

| 端口 | 服务 | 对外 |
|------|------|------|
| **7777** | CCC Hub | 本机 +（历史）局域网；**M1 客户端勿再默认直连** |
| **7775** | Board API | 优先仅本机；由 Hub 反代 |

~~`:4000` / `:4002` 中转已退役，勿再监听、勿再配置。~~

M1 Desktop / 编排 API：**`http://127.0.0.1:17777`**（SSH 隧道）  
2017 本机 Hub：`http://127.0.0.1:7777`  
对话口：`http://192.168.3.140:7788`（M1；勿把对话 SPA 挂到 2017）

---

## 编排执行链（Mac2017）

```text
M1 定稿 → POST /api/desktop/transfer → backlog epic (pending)
  → Engine product（Claude → MiniMax）→ planned work×N
  → Engine dev（OpenCode → 讯飞）→ in_progress → testing
  → reviewer（Claude → MiniMax）+ tester → verified
  → kb → released → epic split_status=done
```

**角色锁**：product = Claude；dev = OpenCode；不可互换（见 [`../runbooks/orchestration-flow.md`](../runbooks/orchestration-flow.md)）。

---

## 并发

| 项 | 值 |
|----|-----|
| live agent 上限 | 默认 **4**；`CCC_MAX_CONCURRENT` 可覆盖（2017 headroom 试 **6**；同仓 OpenCode 仍 **1**） |
| 容量探针 | `python3 scripts/ccc-capacity-probe.py recommend --target-apps 10` |
| 注册默认态 | orch=`CCC` + 业务 apps |

---

## 数据与执行同机

- 业务 git 工作区放在 Server：`~/program/apps/<name>/`
- Engine / 执行器在 Server 上读写这些路径
- 禁止「UI 连 2017、代码与 Engine 仍在 M1」的双脑

---

## 鉴权与网络安全

- Hub：Basic Auth（见 `docs/ccc-hub-ports.md`）；局域网也不得裸奔
- 上游 key：MiniMax / 讯飞只存本机 `~/.ccc/` 与 `~/.config/opencode/`；不对公网暴露
- 第一版非目标：公网入口、多 Server 集群、手机商店分发

### 打不开 :7777 时（Server 本机正常、客户端超时）

1. 在 Server 上确认：`curl -u ccc:ccc http://127.0.0.1:7777/api/desktop/projects`（或 `/api/projects`）
2. 客户端：`ping 192.168.3.116` + `nc -z 192.168.3.116 7777` + 同上 `curl` 打局域网 IP
3. Server：`lsof -nP -iTCP:7777 -sTCP:LISTEN` 应为 `*:7777`（`CCC_CHAT_HOST=0.0.0.0`）；若只绑 `127.0.0.1` 则局域网不可达
4. 仍超时 → 多为 macOS 应用防火墙拦了 Python 入站；或 Hub 刚 kickstart 尚未就绪（等数秒重试）
5. Hub 账号默认：`ccc` / `ccc`  
验收记录：[`../product/hub-shell-wave-a-lan.md`](../product/hub-shell-wave-a-lan.md)（2026-07-21 现网已通）

---

## 产品面优先级

| 面 | 状态 |
|----|------|
| Server + Engine | 主线（编排消费） |
| **CCC Desktop + sidecar + loop-code** | **主产品入口** |
| 网页 Hub | **运维/兼容**（`:7777` 看板/ops；对话远程见 M1 `:7788`） |
| 手机 | 远期 |

---

## 执行器

- **对话方案 Agent（M1）**：loop-code（arm64，sidecar）→ MiniMax  
- **看板开发（Mac2017）**：OpenCode → 讯飞。契约：[`../product/executor-plugins.md`](../product/executor-plugins.md)

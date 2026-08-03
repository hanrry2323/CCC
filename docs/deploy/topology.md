# CCC 部署拓扑 — Server / Client

> **⚠ 更新（T45，2026-08-04）**：本文件主体描述 **2026-08-02 重构定稿前** 的旧双机架构
> （M1 sidecar `:7788` 对话口 / Hub `:7777` 编排）。**现行权威**：`docs/INDEX.md` §0 ——
> **2017 单端 `:7788` 唯一入口**（对话/看板/运维/线路图），M1 7788 实例已退役停用
> （launchd `com.ccc.web-server` 仅 2017 部署）。下方旧口径仅作历史参考，勿据此再起 M1 7788 实例。

> SSOT：服务端与客户端职责。更新日期：2026-08-04（T45 统一 2017:7788 唯一入口）。  
> 相关：[`server-layout.md`](server-layout.md) · [`desktop.md`](desktop.md) · [`../product/dev-channel.md`](../product/dev-channel.md) · [`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md) · [`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md) · [`../product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)

---

## 一句话

**M1 = 对话脑（Desktop + loop-code + ai-loop-router）；Mac2017 = 编排手（Hub + Board + Engine + 业务仓）。**  
中间只交结构化信息流（transfer / flow）。  
**模型出口：ai-loop-router 路由**（三档 `flash`/`Pro`/`code`，上游由 `~/program/ai-loop-router/upstreams.json` 统一管理）。

---

## 角色

| 角色 | 机器 | IP | 职责 |
|------|------|-----|------|
| **Client（对话）** | M1 | `192.168.3.140` | **CCC Desktop + sidecar `:7788` + arm64 loop-code**；本机会话 SSOT；远程浏览器聊亦打此口 |
| **Server（编排）** | Mac2017 | `192.168.3.116` | Hub API、Board、Engine（Claude 扇出）、OpenCode（dev 写码）、业务工作区、上游 API key |
| **Egress（可选）** | 香港 VPS | `124.156.166.72` | HTTP CONNECT 出口；免费多钥拆 IP（`com.ccc.hk-egress-tunnel`） |
| **Client（运维）** | 浏览器 | — | 网页 Hub `:7777`（看板/运维）；**不是**对话入口 |

同一时刻：**只一台 Engine**（Server）。  
**M1 不跑 Engine、不扇出 work、不在业务仓写码**（边界基线）。

---

## 模型出口（三档契约）

| 路径 | 执行器 | 模型路由 | 故障降级 |
|------|--------|----------|----------|
| M1 对话（Desktop → sidecar `:7788`） | loop-code（arm64） | **本机 ai-loop-router** `http://127.0.0.1:4100`（`flash`） | `CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url` |
| Engine product 扇出 | Claude | **M1 ai-loop-router** `AGENT_PLANNER_BASE_URL=http://192.168.3.140:4100` | 同上 fail-open 直连文件 |
| Engine dev 写码 | OpenCode | **M1 ai-loop-router** `:4102`（`code` 档） | 探活失败切直连兜底（见 `opencode.direct.json`） |

> 三档契约：下游只对接 `flash`/`Pro`/`code` 逻辑名，上游由 `ai-loop-router/upstreams.json` 统一路由。  
> 详见 [`../product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「三档契约 + 上游解耦」。

**CCC 仓内 relay/ 已拆出**（2026-08-01），使用独立项目 `~/program/ai-loop-router`（端口 4100/4102）。  
旧 `com.ccc.relay.m1` / `com.ccc.relay.2017` plist 已退役。

---

## 端口

### M1（对话面 + 中转站）

| 端口 | 服务 | 说明 |
|------|------|------|
| **7788** | CCC Agent Sidecar | Desktop **与远程浏览器**对话热路径；launchd `com.ccc.agent-sidecar` KeepAlive |
| **4100** | ai-loop-router | Anthropic 协议转换（flash tier）；`com.ai-loop-router` |
| **4102** | ai-loop-router | OpenAI Chat 协议转换（code tier）；同进程 |
| **17777** | Hub SSH 隧道（本机） | `com.ccc.hub-tunnel`：`ssh -L` → 2017 `:7777`；**Desktop/sidecar 默认 Hub URL** |

Sidecar → **本机 ai-loop-router** `:4100`（主路径，flash）。relay 不可达时 fail-open → `CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`（禁硬编码厂商 URL）。  
Hub 传输：[`../product/hub-ssh-tunnel.md`](../product/hub-ssh-tunnel.md) · 热路径：[`../product/desktop-agent-sidecar.md`](../product/desktop-agent-sidecar.md) · [`desktop.md`](desktop.md) · 双口：[`../product/hub-remote-management.md`](../product/hub-remote-management.md)。

### Mac2017（编排面）

| 端口 | 服务 | 对外 |
|------|------|------|
| **7777** | CCC Hub | 本机 +（历史）局域网；**M1 客户端勿再默认直连** |
| **7775** | Board API | 优先仅本机；由 Hub 反代 |

Mac2017 **不再运行 relay 实例**。所有模型请求通过 `http://192.168.3.140:4100` / `:4102` 走 M1 的 ai-loop-router。

M1 Desktop / 编排 API：**`http://127.0.0.1:17777`**（SSH 隧道）  
2017 本机 Hub：`http://127.0.0.1:7777`  
对话口：**`http://192.168.3.116:7788`**（2017 单端唯一入口；T45：M1 7788 已退役，勿再起）

---

## 编排执行链（Mac2017）

```text
M1 定稿 → POST /api/desktop/transfer → backlog epic (pending)
  → Engine product（Claude → M1 ai-loop-router :4100 → flash 档）→ planned work×N
  → Engine dev（OpenCode → M1 ai-loop-router :4102 → code 档）→ in_progress → testing
  → reviewer（Claude → M1 ai-loop-router :4100 → flash 档）+ tester → verified
  → kb → released → epic split_status=done
```

**角色锁**：product = Claude；dev = OpenCode；不可互换（见 [`../runbooks/orchestration-flow.md`](../runbooks/orchestration-flow.md)）。  
**fail-open 红线**：relay 探活失败一律客户端降级到 `CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`，**绝不** block/skip 任务；未配置则只打日志。

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
- 上游 key 收至 `~/.ccc/relay/upstreams.json`（0600）；`~/.config/opencode/` 为直连兜底
- 第一版非目标：公网入口、多 Server 集群、手机商店分发

### 打不开 :7777 时（Server 本机正常、客户端超时）

1. 在 Server 上确认：`curl -u ccc:ccc http://127.0.0.1:7777/api/desktop/projects`（**不要**用 `/api/health`——Hub 无此路由，404 是预期）
2. M1 优先：`bash scripts/ccc-hub-probe.sh`（默认隧道 `:17777`）；无 auth 得 401、带 auth 得 200 才算通
3. 客户端：`ping 192.168.3.116` + `nc -z 192.168.3.116 7777` + 同上 `curl -u ccc:ccc`
4. Server：`lsof -nP -iTCP:7777 -sTCP:LISTEN` 应为 `*:7777`（`CCC_CHAT_HOST=0.0.0.0`）；若只绑 `127.0.0.1` 则局域网不可达
5. 仍超时 → 多为 macOS 应用防火墙拦了 Python 入站；或 Hub 刚 kickstart 尚未就绪（等数秒重试）
6. Hub 账号默认：`ccc` / `ccc`  
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

- **对话方案 Agent（M1）**：loop-code（arm64，sidecar）→ **本机 ai-loop-router** `:4100`（`flash`）  
- **看板开发（Mac2017）**：OpenCode → **M1 ai-loop-router** `:4102`（`code` 档）。契约：[`../product/executor-plugins.md`](../product/executor-plugins.md)
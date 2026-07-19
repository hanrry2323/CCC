# CCC 部署拓扑 — Server / Client

> SSOT：服务端与客户端职责。更新日期：2026-07-19（架构对齐版）。  
> 相关：[`server-layout.md`](server-layout.md) · [`desktop.md`](desktop.md) · [`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md) · [`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)

---

## 一句话

**M1 = 对话脑（Desktop + loop-code 深度整合为意图工具）；Mac2017 = 编排手（纯消费开发队列）。**  
中间只交结构化信息流（transfer / flow）。  
Mac2017 = 唯一生产服务端（Hub API + Board + Engine + Router + 业务工作区）；网页 Hub = 运维/兼容。

---

## 角色

| 角色 | 机器 | IP | 职责 |
|------|------|-----|------|
| **Client（对话）** | M1 | `192.168.3.140` | **CCC Desktop + sidecar `:7788` + arm64 loop-code** = 对话意图工具；本机会话 SSOT |
| **Server（编排）** | Mac2017 | `192.168.3.116` | Hub API、Board、Engine（Claude Code 扇出）、OpenCode（dev 写码）、ai-loop-router、业务工作区、上游 API key |
| **Client（运维）** | 浏览器 | — | 网页 Hub（降级；看板/运维已迁入 Desktop，见 [`../deprecate-web-board-ops.md`](../deprecate-web-board-ops.md)） |

同一时刻：**只一台生产中转、只一台 Engine**（均在 Server）。  
**M1 不跑 Engine、不扇出 work、不在业务仓写码**（边界基线）。

---

## 端口

### M1（对话面）

| 端口 | 服务 | 说明 |
|------|------|------|
| **7788** | CCC Agent Sidecar | Desktop 对话热路径；launchd `com.ccc.agent-sidecar` KeepAlive |

Sidecar 出口：`ANTHROPIC_BASE_URL=http://192.168.3.116:4000`（→ 2017 Router）。

### Mac2017（编排面）

| 端口 | 服务 | 对外 |
|------|------|------|
| **7777** | CCC Hub | 局域网客户端入口（API host：transfer / flow / board / ops） |
| **7775** | Board API | 优先仅本机；由 Hub 反代 |
| **4000** | ai-loop-router Anthropic | Claude / Anthropic 协议；M1 sidecar 指 |
| **4002** | ai-loop-router OpenAI | OpenCode（dev 写码） |

Server 本机进程优先用 `127.0.0.1:4000/4002`。

Desktop / API：`http://192.168.3.116:7777`（`CCC_SERVER`）  
网页 Hub（运维）：同上，路径 `/`；产品 API 见 `/api/desktop/*`、`/api/board`、`/api/ops`。

---

## 编排执行链（Mac2017）

```text
M1 定稿 → POST /api/desktop/transfer → backlog epic (pending)
  → Engine product 角色（Claude Code 扇出）→ planned work×N
  → Engine dev 角色（OpenCode 写码）→ in_progress → testing
  → reviewer（Claude Code）+ tester（pytest）→ verified
  → kb（git tag / changelog）→ released
  → 全部子卡 released → epic split_status=done
```

**角色锁**：product = Claude Code；dev = OpenCode；不可互换（见 [`../runbooks/orchestration-flow.md`](../runbooks/orchestration-flow.md)）。

---

## 并发

| 项 | 值 |
|----|-----|
| live agent 上限 | **4**（2017 / 16G） |
| 注册默认态 | orch=`CCC` + 业务 apps（见 [`../product/reset-demo-fleet.md`](../product/reset-demo-fleet.md)） |

---

## 数据与执行同机

- 业务 git 工作区放在 Server：`~/program/apps/<name>/`
- Engine / 执行器在 Server 上读写这些路径
- 禁止「UI 连 2017、代码与 Engine 仍在 M1」的双脑

---

## 鉴权与网络安全

- Hub：Basic Auth（见 `docs/ccc-hub-ports.md`）；局域网也不得裸奔
- 中转：密钥只存 Server；不对公网暴露
- 第一版非目标：公网入口、多 Server 集群、手机商店分发

### 打不开 :7777 时（Server 本机正常、客户端超时）

1. 在 Server 上确认：`curl -u ccc:ccc http://127.0.0.1:7777/api/projects`
2. 客户端 `ping 192.168.3.116` 通但 `nc`/浏览器超时 → 多为 macOS 应用防火墙拦了 Python/Node 入站  
   - 系统设置 → 网络 → 防火墙：关闭，或允许 `Python` / `node` 传入  
   - 或：`/usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off`
3. Hub 账号默认：`ccc` / `ccc`（浏览器会弹 Basic Auth）

---

## 产品面优先级

| 面 | 状态 |
|----|------|
| Server + 中转 + Engine | 主线（编排消费） |
| **CCC Desktop（SwiftUI）+ sidecar + loop-code** | **主产品入口**（对话意图工具） |
| 网页 Hub | **运维/兼容**；看板/运维已迁入 Desktop |
| 手机 | 远期；同一 Desktop API |

---

## 执行器

- **对话方案 Agent（M1）**：loop-code（arm64，sidecar 用）
- **看板开发（Mac2017）**：OpenCode（默认）/ python / ollama / cli。契约：[`../product/executor-plugins.md`](../product/executor-plugins.md)

# CCC 部署拓扑 — Server / Client

> SSOT：服务端与客户端职责。更新日期：2026-07-19。  
> 相关：[`server-layout.md`](server-layout.md) · [`desktop.md`](desktop.md) · [`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md)

---

## 一句话

**壳在 Desktop，脑和手在服务器。**  
Mac2017 = 唯一生产服务端（API + Engine + Board + 中转 + 工作区）；  
**CCC Desktop（SwiftUI）** = 主客户端；网页 Hub = 运维/兼容；M1 本机 CLI 可只连服务端中转。

---

## 角色

| 角色 | 机器 | IP | 职责 |
|------|------|-----|------|
| **Server** | Mac2017 | `192.168.3.116` | Desktop API、Board、Engine、ai-loop-router、业务工作区、上游 API key |
| **Client（主）** | 任意 Mac | LAN | **CCC Desktop** → `CCC_SERVER`（默认 `http://192.168.3.116:7777`） |
| **Client（运维）** | 浏览器 | — | 网页 Hub（降级，非产品主入口） |
| **Client（CLI）** | M1 等 | `192.168.3.140` 等 | 本机 Claude/OpenCode **调用**服务端中转；不跑生产 Engine |

同一时刻：**只一台生产中转、只一台 Engine**（均在 Server）。

---

## 端口（Server）

| 端口 | 服务 | 对外 |
|------|------|------|
| **7777** | CCC Hub | 局域网客户端入口 |
| **7775** | Board API | 优先仅本机；由 Hub 反代 |
| **4000** | ai-loop-router Anthropic | Claude / Anthropic 协议；LAN 客户端可指 |
| **4002** | ai-loop-router OpenAI | OpenCode；LAN 客户端可指 |

Server 本机进程优先用 `127.0.0.1:4000/4002`。  
Client 本机 Claude/OpenCode：

```bash
export ANTHROPIC_BASE_URL=http://192.168.3.116:4000
# OpenCode / OpenAI 兼容 → http://192.168.3.116:4002
```

Desktop / API：`http://192.168.3.116:7777`（`CCC_SERVER`）  
网页 Hub（运维）：同上，路径 `/`；产品 API 见 `/api/desktop/*`

---

## 并发

| 项 | 值 |
|----|-----|
| live agent 上限 | **4**（2017 / 16G） |
| 注册默认态 | orch=`CCC` + 唯一 demo app（见 [`../product/reset-demo-fleet.md`](../product/reset-demo-fleet.md)） |

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
| Server + 中转 + Engine | 主线 |
| **CCC Desktop（SwiftUI）** | **主产品入口**（见 `desktop/`） |
| 网页 Hub | **运维/兼容**；非产品主叙事 |
| 手机 | 远期；同一 Desktop API |

---

## 执行器

可插拔：OpenCode（默认）/ python / ollama / cli。契约：[`../product/executor-plugins.md`](../product/executor-plugins.md)。

# CCC 部署拓扑 — Server / Client

> SSOT：服务端与客户端职责。更新日期：2026-07-18。  
> 相关：[`server-layout.md`](server-layout.md) · [`migration-m1-to-2017.md`](migration-m1-to-2017.md)

---

## 一句话

**壳在各端，脑和手在服务器。**  
Mac2017 = 唯一生产服务端（Hub + Engine + Board + 中转 + 工作区）；  
M1 / 桌面 / 浏览器 / 未来手机 = 客户端，只连服务端。

---

## 角色

| 角色 | 机器 | IP | 职责 |
|------|------|-----|------|
| **Server** | Mac2017 | `192.168.3.116` | Hub、Board、Engine、ai-loop-router、业务工作区、上游 API key |
| **Client** | M1（及后续桌面/手机） | `192.168.3.140` 等 | UI、本机 Claude/OpenCode **调用**服务端中转；不跑生产 Engine/中转 |

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

Hub 客户端：`http://192.168.3.116:7777`

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

---

## 产品面优先级

| 面 | 状态 |
|----|------|
| Server + 中转 + Engine | 主线 |
| 桌面多会话（CCC 自有 Tauri） | 主线（P4） |
| 网页 Hub | **过渡客户端**；冻结多路大修 |
| 手机 | 远期；同一 Hub API |

---

## 执行器

可插拔：官方 Claude Code / `CCC/vendor/loop-code`（可选私有）/ OpenCode 等。  
中层只认 Executor 契约；不把任一发行版写成唯一地基。详见后续 `docs/executors/`。

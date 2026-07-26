# CCC Infrastructure — 机器 / 端口 / 服务总览

> 本文档是 CCC 基础设施的权威来源。Claude Code 启动时强制读取。  
> 部署拓扑 SSOT：[`docs/deploy/topology.md`](../docs/deploy/topology.md)  
> 服务端目录：[`docs/deploy/server-layout.md`](../docs/deploy/server-layout.md)  
> 变更端口或拓扑后同步更新本文件。  
> 更新日期：2026-07-26（CCC Relay 回归 + 三档契约；双实例 M1/2017）

---

## 机器清单

| 主机 | IP | 角色 | OS | 说明 |
|------|-----|------|-----|------|
| **Mac 2017** | 192.168.3.116 | **CCC Server** | macOS | Hub / Board / Engine / CCC Relay 2017 / 业务仓（唯一编排生产） |
| **M1** | 192.168.3.140 | **Client** | macOS | Desktop + sidecar + relay.m1 + hub-tunnel；编排连 2017 |
| feiniu | 192.168.3.131 | 生产机 | Ubuntu | HP、medio-0 等（非 CCC 控制面） |

---

## Mac 2017 (192.168.3.116) — CCC Server（编排面）

根目录：`/Users/fan/program`（规范见 server-layout）

| 端口 | 服务 | 说明 |
|------|------|------|
| **7777** | CCC Hub | 编排 API + 看板 UI |
| **7775** | CCC Board API | 任务看板；优先本机；Hub 反代 |
| **4000** | CCC Relay 2017 | `com.ccc.relay.2017`；Anthropic 协议，flash/pro 档；Engine product/reviewer 出口 |
| **4002** | CCC Relay 2017 | openai-chat 协议，code 档；OpenCode dev 写码出口 |

| 路径 | 用途 |
|------|------|
| `/Users/fan/program/CCC` | 主产品 + orch + `relay/` CCC Relay 子系统（现行） |
| `/Users/fan/program/apps/ccc-demo` | 默认 demo app |
| `/Users/fan/program/apps/<name>` | register 的业务仓 |
| `/Users/fan/program/infra/ai-loop-router` | 旧中转站归档（RETIRED；功能已并入 CCC/relay/） |

**live agent 上限：4**

SSH（从 M1）：`ssh mac2017`（user `fan`）

**模型出口（三档契约）**：
- Claude product/reviewer → 本机 CCC Relay `:4000` `flash` 档（主路径）→ OpenCode / MiniMax（fail-open）
- OpenCode dev → 本机 CCC Relay `:4002` `code` 档（主路径）→ 讯飞/智谱（fail-open）

---

## M1 (192.168.3.140) — Client（对话面）

| 端口 | 服务 | 说明 |
|------|------|------|
| **7788** | CCC Agent Sidecar | Desktop 对话热路径；`com.ccc.agent-sidecar` |
| **4000** | CCC Relay M1 | `com.ccc.relay.m1`；对话面模型路由 flash 档 |
| **17777** | Hub SSH 隧道 | `com.ccc.hub-tunnel`；转发到 Mac2017 Hub :7777 |
| 788 | (未使用) | 历史端口，当前不在用 |

**默认路径**：Desktop → sidecar `:7788` → loop-code → **本机 relay `:4000`**（主路径）→ MiniMax（fail-open 兜底）  
**Hub 访问**：`http://127.0.0.1:17777`（SSH 隧道 → Mac2017 Hub :7777）  

客户端环境变量示例（排障用）：

```bash
# 对话面模型出口（默认已走 relay :4000；设此值强制直连）
export ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
export ANTHROPIC_MODEL=MiniMax-M3
```

M1 不跑 Engine、Board、Hub — 这些是 Mac2017 专属（编排面）。

其他本机服务（HP / qb 等）与 CCC Server 无关，各自配置。

---

## feiniu (192.168.3.131) — 生产机

| 端口 | 服务 | 说明 |
|------|------|------|
| 3000 | medio-0 Web | 本地媒体中心 |
| 11434 | ollama bge-m3 | 向量模型（CPU） |
| 18080 | Money Printer Turbo | xianyu 视频生成 |

---

## 各项目端口汇总（CCC）

| 项目 | 生产入口 | 说明 |
|------|----------|------|
| CCC Hub | `http://192.168.3.116:7777`（或 M1 tunnel `:17777`） | Server |
| CCC Relay 2017 | `http://127.0.0.1:4000`（Anthropic）/ `:4002`（openai-chat） | Server 编排出口 |
| CCC Relay M1 | `http://127.0.0.1:4000`（Anthropic） | M1 对话出口 |
| Desktop sidecar | `http://127.0.0.1:7788` | M1 本机对话 |
| ccc-demo | Server `apps/ccc-demo` | 默认唯一 engine app |

---

## 产品默认注册（Server）

| name | role | engine |
|------|------|--------|
| CCC | orch | false |
| ccc-demo | app | true |

详见 [`docs/product/reset-demo-fleet.md`](../docs/product/reset-demo-fleet.md)。

---

## CCC Hub 架构（摘要）

```
scripts/ccc-chat-server.py          # 入口 → Hub :7777
scripts/chat_server/                # 模块化包
└── frontend/                       # Hub SPA（过渡客户端；桌面为主线）
```

- 启动账密默认见 `docs/ccc-hub-ports.md`
- 运维：Hub `#/ops`；自检：`python3 scripts/verify-ccc-hub.py`

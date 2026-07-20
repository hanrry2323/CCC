# CCC Infrastructure — 机器 / 端口 / 服务总览

> 本文档是 CCC 基础设施的权威来源。Claude Code 启动时强制读取。  
> 部署拓扑 SSOT：[`docs/deploy/topology.md`](../docs/deploy/topology.md)  
> 服务端目录：[`docs/deploy/server-layout.md`](../docs/deploy/server-layout.md)  
> 变更端口或拓扑后同步更新本文件。  
> 更新日期：2026-07-20（模型直连；ai-loop-router 退役）

---

## 机器清单

| 主机 | IP | 角色 | OS | 说明 |
|------|-----|------|-----|------|
| **Mac 2017** | 192.168.3.116 | **CCC Server** | macOS | Hub / Engine / Board / 业务仓（唯一生产） |
| M1 | 192.168.3.140 | Client / 移动开发 | macOS | Desktop + sidecar + loop-code；编排连 2017 |
| feiniu | 192.168.3.131 | 生产机 | Ubuntu | HP、medio-0 等（非 CCC 控制面） |

---

## Mac 2017 (192.168.3.116) — CCC Server

根目录：`/Users/fan/program`（规范见 server-layout）

| 端口 | 服务 | 说明 |
|------|------|------|
| **7777** | CCC Hub | 局域网客户端入口 |
| **7775** | CCC Board API | 优先本机；Hub 反代 |
| ~~**4000**~~ | ~~ai-loop-router Anthropic~~ | **已退役**；Claude → MiniMax 直连 |
| ~~**4002**~~ | ~~ai-loop-router OpenAI~~ | **已退役**；OpenCode → 讯飞直连 |

| 路径 | 用途 |
|------|------|
| `/Users/fan/program/CCC` | 主产品 + orch |
| `/Users/fan/program/infra/ai-loop-router` | 中转站归档（RETIRED） |
| `/Users/fan/program/apps/ccc-demo` | 默认 demo app |
| `/Users/fan/program/archive/` | 冷归档 |

**live agent 上限：4**

SSH（从 M1）：`ssh mac2017`（user `fan`）

模型出口：Claude / product → `https://api.minimaxi.com/anthropic`；OpenCode → `xfyun/code`。

---

## M1 (192.168.3.140) — Client

迁切完成后：

| 项 | 状态 |
|----|------|
| 生产中转 :4000/:4002 | **停用**（已退役） |
| 生产 Hub / Engine | **停用**；Desktop 连 `http://192.168.3.116:7777` |
| 本机对话 | sidecar `:7788` + loop-code → MiniMax |
| 本机开发 | 可保留代码仓；不跑生产双脑 |

客户端环境变量示例：

```bash
export ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
export ANTHROPIC_MODEL=MiniMax-M3
```

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
| CCC Hub | http://192.168.3.116:7777 | Server |
| Desktop sidecar | http://127.0.0.1:7788 | M1 本机对话 |
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

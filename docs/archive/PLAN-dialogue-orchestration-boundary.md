# 对话面 / 编排面 架构收口计划

> 依据已定稿契约：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)  
> 文档基线已写入 VISION / Desktop 架构 / connection / transfer-gate / SSOT / STARTUP / CLAUDE（2026-07-19）。  
> **状态（2026-07-19）**：已按全面计划执行（Cursor plan `boundary_architecture_rollout`）。  
> **归档说明**：本文是收口**执行记录**，不是下阶段北星。现网模型出口见 [`../deploy/topology.md`](../deploy/topology.md)（MiniMax/讯飞直连；~~:4000 已退役~~）。下阶段见 [`hub-shell-roadmap.md`](hub-shell-roadmap.md)。

## 目标

| # | 目标 | 出门 |
|---|------|------|
| C1 | 常态对话 **只走本机 sidecar** | 无 Hub `/api/chat` 热路径 |
| C2 | Hub 只服务信息流 | projects / transfer / flow / 可选消息镜像 |
| C3 | 编排面可独立跑 | 2017 `control=enabled`；Engine cwd = 业务仓 |
| C4 | 模型出口对齐 | M1 sidecar → 2017 `:4000` |
| C5 | 验收 B1–B5 | 见边界契约 |

```text
M1: Desktop + Sidecar + loop-code  →  epic（transfer）
2017: Hub + Board + Engine        →  远端开发；flow 回程
中间：仅结构化信息流
```

---

## 阶段执行记录

| 阶段 | 内容 | 状态 |
|------|------|------|
| A | Desktop 禁 Hub chat；`canChat` / `hubReachable` / `canTransfer` | **已做** |
| C | sidecar 默认 Router → `192.168.3.116:4000`；launchd 重装 | **已做** |
| B | PUT = backup；Hub chat `X-CCC-Chat-Role: legacy`；Engine 不读 chat | **已做** |
| D | 2017 `enable --start`；transfer → backlog → fanout | **已做** |
| E | smoke / GO-LIVE B1–B5 / 打包安装 | **已做** |

## 明确不做

云 SaaS；嵌 SDK；改看板语义；会话权威迁回 2017。

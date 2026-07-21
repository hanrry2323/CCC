# CCC 文档索引

> **先读本页再进别的文件。** `docs/` 约 100+ 篇，多数是历史/烟测/专项；**不要按文件名新旧猜权威。**  
> 冲突裁决顺序：`VERSION` → `CHANGELOG` → **VISION** → **边界基线** → 专题 SSOT → 其余。

---

## 0. 现在只认这 6 份（产品/架构）

| 优先级 | 文档 | 管什么 |
|--------|------|--------|
| 1 | [`../VERSION`](../VERSION) + [`../CHANGELOG.md`](../CHANGELOG.md) | 版本事实 |
| 2 | [`VISION.md`](VISION.md) | 对外/对内叙事 |
| 3 | [`product/dialogue-orchestration-boundary.md`](product/dialogue-orchestration-boundary.md) | **对话/编排边界（架构基线）** |
| 4 | [`product/hub-shell-roadmap.md`](product/hub-shell-roadmap.md) | **下阶段北星（壳 + Hub API v1；意图门人审）** |
| 4b | [`product/dev-channel.md`](product/dev-channel.md) | **谁改 CCC / Desktop 模型默认（Cursor · MiniMax）** |
| 5 | [`product/ccc-desktop-architecture.md`](product/ccc-desktop-architecture.md) | Desktop 产品形态 |
| 6 | [`../STARTUP-BRIEF.md`](../STARTUP-BRIEF.md) | Agent 启动省 token |

部署拓扑另加：[`deploy/topology.md`](deploy/topology.md)。控制面：[`CONTROL.md`](CONTROL.md)。

---

## 1. 契约与热路径（按需，仍现行）

| 文档 | 说明 |
|------|------|
| [`product/hub-api-v1.md`](product/hub-api-v1.md) | **Hub API v1 契约**（transfer 幂等 / 投递三态） |
| [`product/hub-remote-management.md`](product/hub-remote-management.md) | **Hub HTTP 远程管理口**（会话分区 / `#/chat`） |
| [`product/transfer-gate.md`](product/transfer-gate.md) | 定稿 → transfer 字段 |
| [`product/flow-events.md`](product/flow-events.md) | 右栏 / SSE |
| [`product/desktop-connection.md`](product/desktop-connection.md) | 连接与本机会话 SSOT |
| [`product/hub-shell-phase-status.md`](product/hub-shell-phase-status.md) | Hub-Shell 分阶段状态板 |
| [`product/hub-shell-phase6-qb.md`](product/hub-shell-phase6-qb.md) | Phase6 真实仓 qb 绿通记录 |
| [`product/desktop-agent-sidecar.md`](product/desktop-agent-sidecar.md) | sidecar / loop-code 热路径 |
| [`product/loop-code-ownership-cut.md`](product/loop-code-ownership-cut.md) | **M1 Desktop 独占 loop-code / 配置切割（战略 SSOT）** |
| [`product/desktop-agent-identity.md`](product/desktop-agent-identity.md) | **Desktop 对话 Agent 身份与心智** |
| [`product/project-as-conversation.md`](product/project-as-conversation.md) | 一项目一对话 |
| [`deploy/desktop.md`](deploy/desktop.md) | 打包与多端版本核对 |
| [`runbooks/app-migrate-register-desktop.md`](runbooks/app-migrate-register-desktop.md) | 业务仓接入操作 |
| [`product/desktop-agent-handoff.md`](product/desktop-agent-handoff.md) | Agent 短交接 |
| [`workspace-binding.md`](workspace-binding.md) | 多项目绑定 |
| [`ccc-hub-ports.md`](ccc-hub-ports.md) | 端口账密 |
| [`architecture-core.md`](architecture-core.md) | Engine/Board 代码分层（改脚本时） |

---

## 2. 路线图谁说了算（重要）

| 文档 | 状态 | 怎么用 |
|------|------|--------|
| **[`product/hub-shell-roadmap.md`](product/hub-shell-roadmap.md)** | **现行北星** | 下阶段开发只认这份 |
| [`roadmap.md`](roadmap.md) | 半归档 | 当前方向已改指 hub-shell；正文大量 v0.19 史实 |
| [`archive/NEXT-DUAL-TRACK.md`](archive/NEXT-DUAL-TRACK.md) | **业务双轨归档** | xianyu/clawmed 拍板记录；**不是** CCC 产品北星 |
| [`archive/next-upgrade-roadmap.md`](archive/next-upgrade-roadmap.md) | **过时** | v0.21→v0.23 |
| [`archive/PLAN-dialogue-orchestration-boundary.md`](archive/PLAN-dialogue-orchestration-boundary.md) | **已执行完** | 收口计划记录 |
| `v1.0-pipeline-plan` 等 | 在 `archive/` | 勿覆盖 VISION |

**INDEX / 口头「下一步」若指向双轨或旧 roadmap，一律改指 `hub-shell-roadmap`。**

---

## 3. 交付已完成、改成「计分/验收」勿当新计划

| 文档 | 说明 |
|------|------|
| [`product/desktop-opencode-parity.md`](product/desktop-opencode-parity.md) | OpenCode 完善度计分（已交付勾选） |
| [`product/desktop-usability-9.5-plan.md`](product/desktop-usability-9.5-plan.md) | 可用性冲刺计划（多为已做） |
| [`product/desktop-flow-rail-ux.md`](product/desktop-flow-rail-ux.md) | 右栏 UX SSOT |
| [`product/deprecate-web-hub.md`](product/deprecate-web-hub.md) | 网页 Hub 降级说明 |

---

## 4. 上手 / 对外 / 运维

| 文档 | 说明 |
|------|------|
| [`GETTING-STARTED.md`](GETTING-STARTED.md) | 安装与第一条闭环 |
| [`INTRO.md`](INTRO.md) · [`USAGE.md`](USAGE.md) | 对外介绍 / 用户分型 |
| [`ops/GO-LIVE.md`](ops/GO-LIVE.md) · [`ops/GO-LIVE-DESKTOP.md`](ops/GO-LIVE-DESKTOP.md) | 上线卡 |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) · [`lessons.md`](lessons.md) | 排障 |
| [`deploy/server-layout.md`](deploy/server-layout.md) | 2017 目录规范 |
| [`deploy/fleet-apps-migration-2026-07.md`](deploy/fleet-apps-migration-2026-07.md) | 五仓迁移（运维史实，非日常） |

---

## 5. 历史归档（已迁入 `docs/archive/`）

一次性烟测、旧升级路线、chat-server v2 计划、2026-07 舰队卫生盘点、milestones、以及 `NEXT-DUAL-TRACK` / `next-upgrade-roadmap` 等已迁入 [`archive/`](archive/README.md)。  
旧路径若仍存在，多为 **跳转 stub** → archive。

**不要**用 archive 内口径覆盖 VISION / 边界 / `hub-shell-roadmap`。

---

## 6. 架构与术语（次级）

| 文档 | 说明 |
|------|------|
| [`STRATEGY-MAP.md`](STRATEGY-MAP.md) | 全景 + 演进史（长） |
| [`GLOSSARY.md`](GLOSSARY.md) | 术语 |
| [`architecture.md`](architecture.md) | 若与 VISION/边界冲突 → 以 VISION/边界为准 |
| [`model-tier-strategy.md`](model-tier-strategy.md) | 模型分层（部分仍写中转，以 topology + 现网 plist 为准） |
| [`../references/red-lines.md`](../references/red-lines.md) | 红线 |
| [`../references/board-task-schema.md`](../references/board-task-schema.md) | 看板任务契约 |

---

*索引修订：2026-07-20 — 收口「多北星」；下阶段唯一指向 `product/hub-shell-roadmap.md`。*

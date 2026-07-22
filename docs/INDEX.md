# CCC 文档索引

> **先读本页再进别的文件。** `docs/` 约 100+ 篇，多数是历史/烟测/专项；**不要按文件名新旧猜权威。**  
> 冲突裁决顺序：`VERSION` → `CHANGELOG` → **VISION** → **边界基线** → 专题 SSOT → 其余。

---

## 0. 现在只认这几份（产品/架构）

> **事实权威（代码/看板/透镜）+ 人机共识以 [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md) 为最新 SSOT。**  
> 其余文档若与它冲突，改其余文档或标「史」，勿并行维护两套「现行真理」。  
> **共识落盘**：你我达成共识 → 先改该文（及 Cursor rule）→ 再改代码；禁止只留在聊天。

| 优先级 | 文档 | 管什么 |
|--------|------|--------|
| 1 | [`../VERSION`](../VERSION) + [`../CHANGELOG.md`](../CHANGELOG.md) | 版本事实 |
| 2 | [`VISION.md`](VISION.md) | 对外/对内叙事 |
| **3** | **[`product/loop-engineer-authority.md`](product/loop-engineer-authority.md)** | **事实权威 + Hub 只读透镜 + 旁路收死（最新）** |
| 4 | [`product/dialogue-orchestration-boundary.md`](product/dialogue-orchestration-boundary.md) | 对话/编排边界与过桥 |
| 5 | [`product/hub-shell-roadmap.md`](product/hub-shell-roadmap.md) | 下阶段北星（壳 + Hub API） |
| 5a | [`product/lpsn-ship-gate.md`](product/lpsn-ship-gate.md) | **v0.60 LPSN 出门门禁**（L→P→S→N） |
| 5b | [`product/dev-channel.md`](product/dev-channel.md) | 谁改 CCC / Desktop 模型默认 |
| 5c | [`product/four-role-fluency-charter.md`](product/four-role-fluency-charter.md) | 四面协作 + 流畅基线 |
| 6 | [`product/ccc-desktop-architecture.md`](product/ccc-desktop-architecture.md) | Desktop 产品形态 |
| 7 | [`../STARTUP-BRIEF.md`](../STARTUP-BRIEF.md) | Agent 启动省 token |

部署拓扑：[`deploy/topology.md`](deploy/topology.md)。控制面：[`CONTROL.md`](CONTROL.md)。

**日常短读**：handoff → identity；**迁仓清扫史**：[`m1-no-second-tree-closeout.md`](product/m1-no-second-tree-closeout.md)（勿当日常真理）。

---

## 1. 契约与热路径（按需，仍现行）

| 文档 | 说明 |
|------|------|
| [`product/lpsn-ship-gate.md`](product/lpsn-ship-gate.md) | **v0.60 LPSN 出门** |
| [`releases/v0.60.0.md`](releases/v0.60.0.md) | LPSN 发布说明 |
| [`product/hub-api-v1.md`](product/hub-api-v1.md) | **Hub API v1 契约**（transfer 幂等 / 投递三态） |
| [`product/hub-remote-management.md`](product/hub-remote-management.md) | **双口远程**：M1 对话 `:7788` + Hub 经隧道 `:17777` |
| [`product/hub-ssh-tunnel.md`](product/hub-ssh-tunnel.md) | **Hub SSH 隧道**：M1 稳定性主路径 |
| [`product/transfer-gate.md`](product/transfer-gate.md) | 定稿 → transfer 字段 |
| [`product/flow-events.md`](product/flow-events.md) | 右栏 / SSE |
| [`product/desktop-connection.md`](product/desktop-connection.md) | 连接与本机会话 SSOT |
| [`product/hub-shell-phase-status.md`](product/hub-shell-phase-status.md) | Hub-Shell 分阶段状态板（现行） |
| [`product/hub-shell-phase6-qb.md`](product/hub-shell-phase6-qb.md) | Phase6 qb 绿通（仍放 product） |
| [`archive/hub-shell-phases/`](archive/hub-shell-phases/) | **phase8+ / wave / fluency 等已归档**（product 仅 stub） |
| [`product/desktop-agent-sidecar.md`](product/desktop-agent-sidecar.md) | sidecar / loop-code 热路径 |
| [`product/loop-code-ownership-cut.md`](product/loop-code-ownership-cut.md) | **M1 Desktop 独占 loop-code / 配置切割（战略 SSOT）** |
| [`product/desktop-agent-identity.md`](product/desktop-agent-identity.md) | **Desktop 对话 Agent 身份与心智** |
| [`product/project-as-conversation.md`](product/project-as-conversation.md) | 一项目一对话 |
| [`deploy/desktop.md`](deploy/desktop.md) | 打包与多端版本核对 |
| [`runbooks/pre-test-dual-host-sync.md`](runbooks/pre-test-dual-host-sync.md) | **测前**双机对齐 + 清右栏/Engine 干扰 |
| [`../references/authority-patrol.jsonl`](../references/authority-patrol.jsonl) | **权威巡查硬卡**（机读；人话报警由 `scripts/ccc-authority-patrol.py`） |
| [`runbooks/app-migrate-register-desktop.md`](runbooks/app-migrate-register-desktop.md) | 业务仓接入操作 |
| [`product/desktop-agent-handoff.md`](product/desktop-agent-handoff.md) | Agent 短交接 |
| [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md) | 事实权威 + Hub 只读透镜 |
| [`product/m1-no-second-tree-closeout.md`](product/m1-no-second-tree-closeout.md) | **M1 无业务第二树清扫收口**（2026-07-21） |
| [`workspace-binding.md`](workspace-binding.md) | 多项目绑定 |
| [`ccc-hub-ports.md`](ccc-hub-ports.md) | 端口账密 |
| [`architecture-core.md`](architecture-core.md) | Engine/Board 代码分层（改脚本时） |
| [`briefs/_TEMPLATE.md`](briefs/_TEMPLATE.md) | **执行 brief 模板**（定稿后另三窗只认 brief） |
| [`briefs/PASTE-OPS.md`](briefs/PASTE-OPS.md) | **工厂派单板**（用户只复制粘贴） |
| [`briefs/`](briefs/) | 进行中 / 已验收 brief（勿散落到仓外） |

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
| [`model-tier-strategy.md`](model-tier-strategy.md) | **已收口 stub** → 平台只认 Cursor；旧文在 archive/retired-tooling |
| [`../references/red-lines.md`](../references/red-lines.md) | 红线 |
| [`../references/board-task-schema.md`](../references/board-task-schema.md) | 看板任务契约 |

---

*索引修订：2026-07-20 — 收口「多北星」；下阶段唯一指向 `product/hub-shell-roadmap.md`。*

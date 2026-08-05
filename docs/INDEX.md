# CCC 文档索引

> **先读本页再进别的文件。** `docs/` 约 100+ 篇，多数是历史/烟测/专项；**不要按文件名新旧猜权威。**  
> 冲突裁决顺序：`VERSION` → `CHANGELOG` → **重构决策定稿 + 契约 v1（§0 #0）** → **VISION** → 专题 SSOT → 其余（旧 `loop-engineer-authority.md` 等已被重构方案取代，仅作史实）。

---

## 0. 现在只认这几份（产品/架构）

> **2026-08-02 架构重构定稿后，事实权威 = 重构决策定稿 + 契约 v1（最高优先级）。**  
> 旧 [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md) 等已被重构方案取代（史），仅作历史追溯；若与重构决策冲突，以重构决策为准。  
> **共识落盘**：你我达成共识 → 先改本 §0 权威链 → 再改代码；禁止只留在聊天。

| 优先级 | 文档 | 管什么 |
|--------|------|--------|
| **0** | **重构决策定稿 + 契约 v1**（qx-map `__archive__/decisions/ccc-refactor-方案-定稿-2026-08-02.md` D1–D10 · `command-post/ccc-refactor-contract-v1-2026-08-02.md`） | **最高优先级**：薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端 + 任意设备壳；§2 状态机 / §7 执行体注册表 / §8 任意设备=壳 |
| 1 | [`../VERSION`](../VERSION) + [`../CHANGELOG.md`](../CHANGELOG.md) | 版本事实（v0.70.0 架构重构） |
| 2 | [`VISION.md`](VISION.md) | 对外/对内叙事 |
| 3 | [`architecture.md`](architecture.md) | 架构概览（新栈 `server/`） |
| 4 | [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md) | **已被重构方案取代（史）**——旧事实权威 + Hub 只读透镜，仅作历史追溯 |
| 5 | [`product/dialogue-orchestration-boundary.md`](product/dialogue-orchestration-boundary.md) | **已被重构方案取代（史）**——旧对话/编排边界 |
| 5b | [`product/dev-channel.md`](product/dev-channel.md) | 谁改 CCC：开发工具（Claude/OpenCode）合入 · Desktop 禁改仓 |
| 6 | [`product/ccc-desktop-architecture.md`](product/ccc-desktop-architecture.md) | Desktop 产品形态（任意设备壳之一） |
| 7 | [`../STARTUP-BRIEF.md`](../STARTUP-BRIEF.md) | Agent 启动省 token（已按终态重写） |
| 8 | [`../CLAUDE.md`](../CLAUDE.md) | 平台开发硬规则 + 开发命令（已按新栈重写） |

部署拓扑：[`deploy/topology.md`](deploy/topology.md)。2017 布局：[`deploy/server-layout.md`](deploy/server-layout.md)。

**重构收口任务卡**：[`dispatch/T31`](dispatch/T31-refactor-closeout-docs-baseline.md)～[`T35`](dispatch/T35-refactor-closeout-hangover-regression.md)（文档基线 / Engine 真派发 / 硬编码 / 死码 / 回归）。  
**自动化基建（T52）**：[`automation-base.md`](automation-base.md)（出卡模板 / 一键放行 / 壳复验 / 卡头门禁 CI+pre-commit）。  
**现行开发方向（2026-08-04 收口）**：双阶段模型——自研期 Codex 出卡驱动、业务期壳直聊 Agent；任务卡体系规则（索引/命名/大卡小卡）与前端四板块架构见 qx-map `__archive__/decisions/`（双阶段运行模型 / 任务卡体系规则定稿 / 前端四板块架构定稿）。  
**日常短读**：本 §0 → `architecture.md` → `STARTUP-BRIEF.md`。

---

## 1. 契约与热路径（按需，仍现行）

| 文档 | 说明 |
|------|------|
| [`product/lpsn-ship-gate.md`](product/lpsn-ship-gate.md) | **v0.60 LPSN 出门** |
| [`releases/v0.64.0.md`](releases/v0.64.0.md) | **现行** 意图卡供给（含原计划 0.65/0.66） |
| [`references/intent-card-sop.md`](../references/intent-card-sop.md) | **转意图卡 SOP** |
| [`product/desktop-flow-rail-ux.md`](product/desktop-flow-rail-ux.md) | 右栏：看板计数 + 意图卡链 |
| [`releases/v0.63.0.md`](releases/v0.63.0.md) | bg nudge + KPI 缩小 |
| [`releases/v0.62.0.md`](releases/v0.62.0.md) | reviewer `--bg` + bg_sessions + Hub/Desktop |
| [`releases/v0.61.0.md`](releases/v0.61.0.md) | 三档契约 + fleet + 双机门禁 |
| [`releases/v0.60.1.md`](releases/v0.60.1.md) | Desktop 发版 + 运维后勤对齐 + 产线闸门 |
| [`releases/v0.60.0.md`](releases/v0.60.0.md) | LPSN 发布说明 |
| [`product/hub-api-v1.md`](product/hub-api-v1.md) | **Hub API v1 契约**（transfer 幂等 / 投递三态） |
| [`product/hub-remote-management.md`](product/hub-remote-management.md) | **双口远程（史）**：旧 M1 对话 `:7788` 已退役；现行 **2017 单端 `:7788`** 唯一入口 |
| [`product/hub-ssh-tunnel.md`](product/hub-ssh-tunnel.md) | **Hub SSH 隧道（史）**：旧 M1 稳定性路径；现行统一 2017 直连 |
| [`product/transfer-gate.md`](product/transfer-gate.md) | 转意图卡 → transfer_gate |
| [`product/flow-events.md`](product/flow-events.md) | 右栏 / SSE |
| [`product/desktop-connection.md`](product/desktop-connection.md) | 连接与本机会话 SSOT |
| [`product/hub-shell-phase-status.md`](product/hub-shell-phase-status.md) | Hub-Shell 分阶段状态板（现行） |
| [`product/hub-shell-phase6-qb.md`](product/hub-shell-phase6-qb.md) | Phase6 qb 绿通（仍放 product） |
| [`archive/hub-shell-phases/`](archive/hub-shell-phases/) | **phase8+ / wave / fluency 等已归档**（product 仅 stub） |
| [`product/desktop-agent-sidecar.md`](product/desktop-agent-sidecar.md) | sidecar / loop-code 热路径 |
| [`product/loop-code-ownership-cut.md`](product/loop-code-ownership-cut.md) | M1 Desktop 独占 loop-code / 配置切割（切割决策现行；**定位 SSOT 已移** authority「三层架构与 loop-code 槽位化」） |
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
| **[`roadmap.md`](roadmap.md)「当前方向」+ §0 重构决策** | **现行北星** | v0.70 薄驱动 Engine + 2017 单端 + 任务卡；下阶段只认这份 |
| [`CURSOR.md`](../CURSOR.md) · `.cursor/rules/` | **Cursor / 席位现况** | 2026-08-05：Claude Code 执行体 · OpenCode 禁用 |
| [`product/hub-shell-roadmap.md`](product/hub-shell-roadmap.md) | **史（Hub 时期北星）** | 多端壳+Hub API 旧规划；已被 2017 单端重构取代 |
| [`roadmap.md`](roadmap.md) 历史正文 | 半归档 | v0.19 等史实，勿覆盖「当前方向」 |
| [`archive/NEXT-DUAL-TRACK.md`](archive/NEXT-DUAL-TRACK.md) | **业务双轨归档** | **不是** CCC 产品北星 |
| [`archive/next-upgrade-roadmap.md`](archive/next-upgrade-roadmap.md) | **过时** | v0.21→v0.23 |

**INDEX / 口头「下一步」若指向 Hub / hub-shell / 双轨旧文，一律改指 §0 + `roadmap.md` 当前方向 + `CURSOR.md`。**

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
| [`architecture.md`](architecture.md) | 架构概览（新栈 `server/`；若与重构决策冲突 → 以重构决策为准） |
| [`model-tier-strategy.md`](model-tier-strategy.md) | **已收口 stub** → 平台走开发工具（Claude/OpenCode）；旧文在 archive/retired-tooling |
| [`../references/red-lines.md`](../references/red-lines.md) | 红线 |
| [`../references/board-task-schema.md`](../references/board-task-schema.md) | 任务卡文档契约 |

---

*索引修订：2026-08-03 — T31 文档基线切到新架构；权威链顶部改为「重构决策定稿 + 契约 v1」，旧 `loop-engineer-authority.md` 等降级为史。*

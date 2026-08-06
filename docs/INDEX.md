# CCC 文档索引

> **先读本页再进别的文件。** `docs/` 约 100+ 篇，多数是历史/烟测/专项；**不要按文件名新旧猜权威。**  
> 冲突裁决顺序：`VERSION` → `CHANGELOG` → **重构决策定稿 + 契约 v1（§0 #0）** → **VISION** → 专题 SSOT → 其余（旧 `loop-engineer-authority.md` 等已被重构方案取代，仅作史实）。  
> **怎么写文档 / 怎么注册项目 / 卡怎么命名**：[`DOC-PROTOCOL.md`](DOC-PROTOCOL.md)（§2 命名定死）· [`projects/registry.yaml`](projects/registry.yaml)。

---

## 0. 现在只认这几份（产品/架构）

> **2026-08-02 架构重构定稿后，事实权威 = 重构决策定稿 + 契约 v1（最高优先级）。**  
> 旧 [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md) 等已被重构方案取代（史），仅作历史追溯；若与重构决策冲突，以重构决策为准。  
> **共识落盘**：你我达成共识 → 先改本 §0 权威链 → 再改代码；禁止只留在聊天。

### 北星双核心（2026-08-07 · 冲突以此为准）

> **一句话**：一个主 IDE 谈意图 → `ccc-plan` 确认后自动拆卡入队 → Engine+硬门禁静默跑 → 只在 RED 或待合入时找人 → 人审 diff 后「合入批准」。

| # | 核心 | 成功标准 |
|---|------|----------|
| **A** | 只跟一个主 IDE 谈方案 | 确认 `ccc-plan` → `plan-to-cards` 自动多卡；禁止一张张聊着出卡 |
| **B** | CCC = 代码质量门 | 绿静默；质量靠机械门禁/CI/机审 exit code；人只审 diff /「合入批准」 |

**反目标（禁止当产品演进）**：新增验收同义句、席位表、AGENTS 长禁令、看板列解释文、为教 Agent 堆 SOP。缺口进 [`roadmap.md`](roadmap.md) 挂账，不写心智补丁。  
**进度真值**：只认 2017 `:7788` board API；取证认 `origin/codex/<stem>`（见 `scripts/card-evidence.sh`）。  
**竖切入口**：[`product/north-star-slice.md`](product/north-star-slice.md)。

| 优先级 | 文档 | 管什么 |
|--------|------|--------|
| **0** | **重构决策定稿 + 契约 v1**（qx-map `__archive__/decisions/ccc-refactor-方案-定稿-2026-08-02.md` D1–D10 · `command-post/ccc-refactor-contract-v1-2026-08-02.md`） | **最高优先级**：薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端 + 任意设备壳；§2 状态机 / §7 执行体注册表 / §8 任意设备=壳 |
| 1 | [`../VERSION`](../VERSION) + [`../CHANGELOG.md`](../CHANGELOG.md) | 版本事实（v0.70.0 架构重构） |
| 2 | [`VISION.md`](VISION.md) | 对外/对内叙事 |
| 2b | [`DOC-PROTOCOL.md`](DOC-PROTOCOL.md) | **文档写入 + 任务卡命名（硬·定死）**：落点表；优先 `plan-to-cards`；单卡 `new-card.sh` |
| 2b2 | [`product/north-star-slice.md`](product/north-star-slice.md) | **北星竖切**：ccc-plan → 入队 → ready_for_merge → 合入批准 |
| 2c | [`projects/registry.yaml`](projects/registry.yaml) | **项目注册唯一事实源**（前缀 / 路径 / taskable）；每项目一页见 `projects/<prefix>/README.md` |
| 3 | [`architecture.md`](architecture.md) | 架构概览（新栈 `server/`） |
| 4 | [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md) | **已被重构方案取代（史）**——旧事实权威 + Hub 只读透镜，仅作历史追溯 |
| 5 | [`product/dialogue-orchestration-boundary.md`](product/dialogue-orchestration-boundary.md) | **已被重构方案取代（史）**——旧对话/编排边界 |
| 5b | [`product/dev-channel.md`](product/dev-channel.md) | 谁改 CCC；两层验收 |
| 5b2 | [`product/hub-context-sop.md`](product/hub-context-sop.md) | 中枢出卡前了解项目（本仓本地 / 禁业务 ssh 深挖） |
| 5c | [`product/accept-board-sop.md`](product/accept-board-sop.md) | 「验收看板」= **合入批准** 别名（人审 diff） |
| 5d | [`product/machine-audit-flow.md`](product/machine-audit-flow.md) | 2017 机审流程 + 看板「机审」栏 |
| 6 | [`product/ccc-desktop-architecture.md`](product/ccc-desktop-architecture.md) | Desktop 产品形态（任意设备壳之一） |
| 7 | [`../STARTUP-BRIEF.md`](../STARTUP-BRIEF.md) | Agent 启动省 token（已按终态重写） |
| 8 | [`../CLAUDE.md`](../CLAUDE.md) | 平台开发硬规则 + **开仓双模式（中枢/执行体）** + 开发命令 |

部署拓扑：[`deploy/topology.md`](deploy/topology.md)。2017 布局：[`deploy/server-layout.md`](deploy/server-layout.md)。

**重构收口任务卡**：[`dispatch/T31`](dispatch/T31-refactor-closeout-docs-baseline.md)～[`T35`](dispatch/T35-refactor-closeout-hangover-regression.md)（文档基线 / Engine 真派发 / 硬编码 / 死码 / 回归）。  
**自动化基建（T52）**：[`automation-base.md`](automation-base.md)（出卡模板 / 一键放行 / 壳复验 / 卡头门禁 CI+pre-commit）。  
**现行开发方向（2026-08-04 收口）**：双阶段模型——自研期 Codex 出卡驱动、业务期壳直聊 Agent；任务卡体系规则（索引/命名/大卡小卡）与前端四板块架构见 qx-map `__archive__/decisions/`。  
**日常短读**：本 §0 → [`DOC-PROTOCOL.md`](DOC-PROTOCOL.md) → `architecture.md` → `STARTUP-BRIEF.md`。

---

## 1. 契约与热路径（按需）

> **Hub / sidecar / 旧 releases 条目均为史**；现行热路径：任务卡 + `server/` + 2017 `:7788` 看板/运维 + M1 IDE。

| 文档 | 说明 |
|------|------|
| [`product/dev-channel.md`](product/dev-channel.md) | **现行** 开发通道 / 老板面 |
| [`product/hub-context-sop.md`](product/hub-context-sop.md) | **现行** 中枢了解项目 / 出卡前 6 步 |
| [`product/accept-board-sop.md`](product/accept-board-sop.md) | **现行** M1「验收看板」终验 |
| [`../.ccc/infrastructure.md`](../.ccc/infrastructure.md) | **现行** 机器/端口总览 |
| [`deploy/topology.md`](deploy/topology.md) | **现行** 短拓扑 |
| [`automation-base.md`](automation-base.md) | 出卡/门禁基建 |
| [`references/intent-card-sop.md`](../references/intent-card-sop.md) | 转意图卡 SOP |
| [`product/hub-api-v1.md`](product/hub-api-v1.md) | **史** Hub API |
| [`product/hub-ssh-tunnel.md`](product/hub-ssh-tunnel.md) | **史** Hub 隧道 |
| [`product/hub-shell-phase-status.md`](product/hub-shell-phase-status.md) | **史** Hub-Shell |
| [`product/desktop-agent-sidecar.md`](product/desktop-agent-sidecar.md) | **史** sidecar（Desktop 暂缓） |
| [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md) | **史**（已被 §0 取代） |
| [`briefs/_TEMPLATE.md`](briefs/_TEMPLATE.md) | 执行 brief 模板 |
| [`briefs/`](briefs/) | brief 目录 |

其余 Hub 时期 releases / flow-rail / Desktop 打包文 → 仅 Desktop 恢复时查阅；日常勿当现行。

## 2. 路线图谁说了算（重要）

| 文档 | 状态 | 怎么用 |
|------|------|--------|
| **[`roadmap.md`](roadmap.md)「当前方向」+ §0 重构决策** | **现行北星** | v0.70 薄驱动 Engine + 2017 单端 + 任务卡；下阶段只认这份 |
| [`CURSOR.md`](../CURSOR.md) · `.cursor/rules/` | **Cursor / 席位现况** | 2026-08-06：开仓双模式见 CLAUDE.md · HTTP 看板主路径 · Desktop 暂缓 |
| [`product/hub-shell-roadmap.md`](product/hub-shell-roadmap.md) | **史（Hub 时期北星）** | 多端壳+Hub API 旧规划；已被 2017 单端重构取代 |
| [`archive/roadmap-history-v0.19-v0.26.md`](archive/roadmap-history-v0.19-v0.26.md) | **史** | 从 roadmap.md 迁出的 v0.19 等长史；勿覆盖「当前方向」 |
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

# CCC 保留清单（2026-08-02）

> 关联方案：`__archive__/decisions/ccc-refactor-方案-定稿-2026-08-02.md`
> 归档位置：`docs/archive/ccc-legacy-2026-08-02/`
> 验收人：Codex

---

## 一、保留项

### 1. 根目录权威文件（10）

| 文件 | 保留理由 |
|------|----------|
| `README.md` | 项目简介 |
| `CLAUDE.md` | 工程红线、架构核心、开发命令—— **不改** |
| `STARTUP-BRIEF.md` | 启动摘要 |
| `CONTRIBUTING.md` | 贡献指南 |
| `SKILL.md` | 注入 prompt 总纲 |
| `CHANGELOG.md` | 版本历史 |
| `SSOT.md` | 单一事实来源 |
| `ONBOARDING.md` | 上手引导 |
| `SECURITY.md` | 安全策略 |
| `AUDIT.md` | 审计记录 |

### 2. `references/` — 红线/SOP/契约（18 文件，全部保留）

| 文件 | 保留理由 |
|------|----------|
| `red-lines.md` | 18 红线 + X/R 系列—— **权威基线** |
| `board-task-schema.md` | 跨 IDE 看板契约—— **权威基线** |
| `intent-chain-dev-sop.md` | 意图链开发 SOP |
| `intent-proposal-sop.md` | 方案写作 SOP |
| `intent-card-sop.md` | 转意图卡 SOP |
| `align-baseline-sop.md` | 对齐基线 SOP |
| `abnormal-solve-sop.md` | 异常解决 SOP |
| `board-auto-repair-sop.md` | 看板自修复 SOP |
| `post-exhaust-epic-optimize-sop.md` | 飞后优化 SOP |
| `code-review-standard.md` | 代码审查标准 |
| `file-contract.md` | 文件契约 |
| `commit-folder-hygiene-sop.md` | 提交卫生 SOP |
| `transfer-playbook-qb.md` | 转移手册 |
| `finalize-transfer-sop.md` | 转移收口 SOP |
| `adapters/runtime-opencode.md` | OpenCode 运行时适配器 |
| `examples/qxo-audit-frontend.md` | 审计前端示例 |
| `prompts/`（3 个 prompt） | 技能 prompt 库 |
| `skills/`（4 个 skill 定义） | 技能定义库 |

### 3. `skills/` — Skill 定义（9 文件，全部保留）

所有 skill 定义（ccc-dev, ccc-product, ccc-audit, ccc-ops, ccc-regress, ccc-tester, ccc-reviewer, ccc-kb, README）—— **Skill 库，改造范围外**

### 4. `templates/` — 模板（11 文件，全部保留）

所有模板（plan, phases, report, verdict, AGENTS, 等）—— **Engine 运行时依赖**

### 5. `docs/` — 权威文档（22 文件）

| 文件 | 保留理由 |
|------|----------|
| `VISION.md` | **INDEX §0 #2** — 对外叙事 |
| `INDEX.md` | **文档索引 SSOT** |
| `architecture-core.md` | **INDEX §1** — Engine/Board 代码分层 |
| `architecture.md` | **INDEX §6** — 架构概览 |
| `CONTROL.md` | **INDEX §0** — 控制面 |
| `config.md` | 配置参考 |
| `TROUBLESHOOTING.md` | **INDEX §4** — 排障 |
| `GETTING-STARTED.md` | **INDEX §4** — 安装与首条闭环 |
| `INTRO-WALKTHROUGH.md` | 引导教程 |
| `ccc-hub-ports.md` | **INDEX §1** — 端口账密 |
| `lessons.md` | **INDEX §4** — 经验教训 |
| `model-tier-strategy.md` | **INDEX §6** — 模型策略 |
| `vertical-qx.md` | 垂直场景 |
| `workspace-binding.md` | **INDEX §1** — 多项目绑定 |
| `STRATEGY-MAP.md` | **INDEX §6** — 全景演进史 |
| `GLOSSARY.md` | **INDEX §6** — 术语 |
| `INTRO.md` | **INDEX §4** — 对外介绍 |
| `USAGE.md` | **INDEX §4** — 用户分型 |
| `roadmap.md` | **INDEX §2** — 半归档但保留 |
| `program-housekeeping.md` | 服务端布局规范 |
| `observability.md` | **可观测性 SSOT** |
| `NEXT-DUAL-TRACK.md` | 跳转 stub（避免断链） |

### 6. `docs/adr/` — 架构决策记录（5 文件，全部保留）

ADR 001-005 + F2-vs-R12-redundancy—— **决策记录，保留追溯**

### 7. `docs/releases/` — 版本发布（15 文件，全部保留）

v0.42.1 到 v0.66.1—— **版本历史，保留追溯**

### 8. `docs/archive/` — 已归档（全部保留）

已有归档内容保持不动。

### 9. `docs/deploy/` — 部署（6 文件，全部保留）

| 文件 | 保留理由 |
|------|----------|
| `topology.md` | **部署拓扑 SSOT** |
| `desktop.md` | 打包与多端版本 |
| `server-layout.md` | 2017 目录规范 |
| `migration-m1-to-2017.md` | 迁移记录 |
| `fleet-apps-migration-2026-07.md` | 五仓迁移史实 |
| `dual-host-version-check.md` | 双机版本核对 |

### 10. `docs/executors/` — 执行器（2 文件，全部保留）

| 文件 | 保留理由 |
|------|----------|
| `overview.md` | 执行器概述 |
| `loop-code.md` | loop-code 热路径 |

### 11. `docs/ops/` — 运维（3 文件，全部保留）

| 文件 | 保留理由 |
|------|----------|
| `GO-LIVE.md` | **上线卡** |
| `GO-LIVE-DESKTOP.md` | **Desktop 上线卡** |
| `hub-boss-voice.md` | 运维参考 |

### 12. `docs/runbooks/` — 运维手册（3 文件，全部保留）

| 文件 | 保留理由 |
|------|----------|
| `pre-test-dual-host-sync.md` | **INDEX §1** — 测前双机对齐 |
| `app-migrate-register-desktop.md` | **INDEX §1** — 业务仓接入 |
| `orchestration-flow.md` | 编排流程 |

### 13. `docs/briefs/` — 保留 5 份（INDEX §0 引用）

| 文件 | 保留理由 |
|------|----------|
| `_TEMPLATE.md` | **INDEX §1** — 执行 brief 模板 |
| `PASTE-OPS.md` | **INDEX §1** — 工厂派单板 |
| `2026-07-27-ccc-production-readiness.md` | **INDEX §0 #5d** — 生产级三层出门 |
| `2026-07-27-golden-path-evidence.md` | **INDEX §0 #5f** — Layer1 金路径探针 |
| `2026-07-27-qb-domain-ship-gate.md` | **INDEX §0 #5g** — qb 业务域 KPI |

### 14. `docs/dev-packets/` — 保留 3 份

| 文件 | 保留理由 |
|------|----------|
| `README.md` | **INDEX §0 #5e** — 指令包 SSOT |
| `_TEMPLATE.md` | 新包模板 |
| `PRODUCTION-DELIVERY-ROUNDS.md` | 交付轮次参考 |

### 15. `docs/relay/` — 保留 1 份

| 文件 | 保留理由 |
|------|----------|
| `KEY-POOL.md` | 钥池手册（配置参考） |

### 16. `docs/assets/intro/` — 保留 1 份

| 文件 | 保留理由 |
|------|----------|
| `README.md` | 截图占位说明 |

### 17. `docs/product/` — 保留 33 份（权威基线）

| 文件 | 保留理由 |
|------|----------|
| `loop-engineer-authority.md` | **INDEX §0 #3** — 事实权威 SSOT |
| `dialogue-orchestration-boundary.md` | **INDEX §0 #4** — 对话/编排边界 |
| `dev-channel.md` | **INDEX §0 #5b** — 开发通道 |
| `role-formation.md` | 角色形成机制 |
| `desktop-agent-handoff.md` | **INDEX §1** — Agent 短交接 |
| `desktop-agent-sidecar.md` | **INDEX §1** — sidecar 热路径 |
| `desktop-agent-identity.md` | **INDEX §1** — 身份心智 |
| `desktop-connection.md` | **INDEX §1** — 连接 SSOT |
| `desktop-flow-rail-ux.md` | **INDEX §1, §3** — 右栏 UX SSOT |
| `hub-api-v1.md` | **INDEX §1** — Hub API v1 契约 |
| `hub-ssh-tunnel.md` | **INDEX §1** — Hub SSH 隧道 |
| `hub-remote-management.md` | **INDEX §1** — 双口远程 |
| `hub-shell-roadmap.md` | **INDEX §0 #5, §2** — 北星路线图 |
| `flow-events.md` | **INDEX §1** — 右栏/SSE |
| `transfer-gate.md` | **INDEX §1** — 转卡门禁 |
| `context-manifest.md` | 上下文清单 |
| `ccc-desktop-architecture.md` | **INDEX §0 #6** — Desktop 产品形态 |
| `ccc-new-architecture-overview.md` | 新架构草案（活跃） |
| `stress-kpi-loop.md` | KPI 循环 |
| `project-agent-brain.md` | 项目代理大脑 |
| `lpsn-ship-gate.md` | **INDEX §0 #5a** — v0.60 出门门禁 |
| `proactive-triggers.md` | 主动触发 |
| `four-role-fluency-charter.md` | **INDEX §0 #5c** — 四面协作 |
| `cursor-model-routing.md` | 模型路由 |
| `executor-plugins.md` | 执行器插件 |
| `project-as-conversation.md` | **INDEX §1** — 一项目一对话 |
| `desktop-opencode-parity.md` | **INDEX §3** — OpenCode 完善度 |
| `desktop-usability-9.5-plan.md` | **INDEX §3** — 可用性计划 |
| `reset-demo-fleet.md` | 演示舰队重置 |
| `hub-shell-phase-status.md` | **INDEX §1** — 分阶段状态板（现行） |
| `hub-shell-phase6-qb.md` | **INDEX §1** — Phase6 qb 绿通 |
| `loop-code-ownership-cut.md` | **INDEX §1** — 切割决策（现行） |
| `m1-no-second-tree-closeout.md` | **INDEX §0** — M1 清扫收口史 |

---

## 二、归档项

### 1. `docs/briefs/` → `archive/ccc-legacy-2026-08-02/briefs/`（53 文件）

全部为已完成改造前的旧任务 briefs（F-系列、H-系列、KPI-系列、应力测试、min-pipeline 等），不再作为现行权威。

### 2. `docs/intent-proposals/` → `archive/ccc-legacy-2026-08-02/intent-proposals/`（7 文件）

stage5/stage6 烟测方案，全部已完成闭环。

### 3. `docs/dev-packets/` → `archive/ccc-legacy-2026-08-02/dev-packets/`（16 文件）

001-016 开发指令包，全部已完成交付。

### 4. `docs/dispatch/` → `archive/ccc-legacy-2026-08-02/dispatch/`（17 文件）

2026-08-01 squad 分派任务卡，单次任务协议。

### 5. `docs/stability/` → `archive/ccc-legacy-2026-08-02/stability/`（3 文件）

2026-07-24 稳定性修复记录，已过时。

### 6. `docs/product/` → `archive/ccc-legacy-2026-08-02/product/`（25 文件）

旧阶段协议（hub-shell-phase8~17）、已关闭子任务（loop-code-ownership-cut closeout/fluency）、旧重构方案（ccc-refactor-stage2~4）——被本方案取代。

### 7. `docs/relay/` → `archive/ccc-legacy-2026-08-02/relay/`（1 文件）

`DEPLOY-2017.md`——显式标记为已废弃（relay 已拆出，走 M1 ai-loop-router）。

### 8. `docs/` 根 → `archive/ccc-legacy-2026-08-02/`（3 文件）

| 文件 | 理由 |
|------|------|
| `CCC-代码质量提升开发方案-2026-07-24.md` | 旧方案，被本方案取代 |
| `CCC-项目深度评估报告-2026-07-24.md` | 旧评估，已过时 |
| `CCC-代码质量下一步修复方案-2026-07-24.md` | 旧方案，被本方案取代 |

### 9. T34 追加归档（2026-08-03）

| 路径 | 文件数 | 理由 |
|------|--------|------|
| `archive/ccc-legacy-2026-08-02/orphan-shell-web/` | 4 | 旧 web shell 孤儿文件（index.html/app.js/chat.js/style.css），T34 从 server/web 白名单摘除 |
| `archive/ccc-legacy-2026-08-02/tauri-desktop-legacy/src-tauri/` | 27 | 旧 Tauri 桌面后端（Rust），T34 归档（Desktop 已迁 Swift） |

### 10. T35 追加归档（2026-08-03）

| 路径 | 文件数 | 理由 |
|------|--------|------|
| `archive/legacy-retired-2026-08-02/tests-scripts/` | 100+ | 旧 `tests/scripts/` 全部测试已退役 `scripts/` 系统，conftest 把 scripts/ 加 sys.path 导致 66 个 collection error；随 scripts/ 退役一并归档 |
| `archive/legacy-retired-2026-08-02/tests-integration/` | 2 | 旧 `tests/integration/` 引用已退役 scripts/ccc-board.py；归档 |
| `archive/legacy-retired-2026-08-02/tests-e2e/` | 12 | 旧 `tests/e2e/*.sh` 引用已退役 scripts/；归档（CI e2e job 一并移除） |

---

## 三、不确定项

无。所有文档均能按上述标准明确归类。

---

## 四、归档统计

| 目录 | 归档文件数 |
|------|-----------|
| briefs/ | 53 |
| intent-proposals/ | 7 |
| dev-packets/ | 16 |
| dispatch/ | 17 |
| stability/ | 3 |
| product/ | 25 |
| relay/ | 1 |
| docs-root/ | 3 |
| orphan-shell-web/（T34 追加） | 4 |
| tauri-desktop-legacy/（T34 追加） | 27 |
| tests-scripts/（T35 追加） | 100+ |
| tests-integration/（T35 追加） | 2 |
| tests-e2e/（T35 追加） | 12 |
| **合计** | **274+** |
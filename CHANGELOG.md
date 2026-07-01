# Changelog

All notable changes to CCC (Codex Claude Collaboration) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0-dev] - 2026-07-01

### Added
- README.md (项目门面 — 框架定位 + 快速上手)
- LICENSE (MIT)
- VERSION (0.3.0-dev)
- docs/architecture.md (4 层抽象 L4-L0 深度说明)
- docs/adr/001-protocol-layer.md (三角色 Protocol 抽象 ADR)
- docs/adr/002-runtime-adapter.md (Runtime Adapter Pattern ADR)
- docs/adr/003-scheduler-adapter.md (Scheduler Adapter Pattern ADR)
- examples/qxo-audit-frontend.md (qx-observer 调研任务三轮回合实战案例)
- 本地 git 仓 + 初始 commit + tag v0.3.0-dev

### Validated (经过 8 次实战验证)
- audit-frontend-and-locate-loopcode (调研类, claude-p 200 USD, 最终 PASS)
- fix-conditional-pass-warnings (修订类, claude-p 200 USD)
- push-audit-frontend-finalization (push 类, claude-p 30 USD)
- write-lesson-20 (Lesson 沉淀, claude-p 30 USD)
- clean-lessons-noise-rows (清理类, claude-p 20 USD)
- push-lesson20-and-noise-cleanup (push 类, claude-p 30 USD)
- distill-ccc-workflow-summary (沉淀类, claude-p 30 USD)
- accept-prior-cleanup-and-qb-sync (验收类 — 早期失败案例, 触发 Lesson 18)
- fix-verdict-fail-2-critical (早期修复 — 触发 Lesson 18 沉淀)

### Red Lines Verified (红线已验证有效)
- Planner 越界 = Critical (Lesson 18)
- mavis session new C6 = Critical (Lesson 19, 红线 8)
- 默认预算 200 USD (5 USD 历史 bug 已修)
- 一个 phase 一个 commit (红线 4)
- phases.json 必写全 (红线 5)

## [0.2.x] - 2026-06-30 之前

### Internal Prototype
- 早期间脚本集阶段
- 多个项目实验性使用 (qx-observer / qb / xianyu)
- 形成 templates/ + skills/ + projects/ 雏形

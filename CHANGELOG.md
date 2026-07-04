# Changelog

All notable changes to CCC (Codex Claude Collaboration) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-07-04

### Added
- `scripts/ccc` — 统一 CLI 入口（status/search/init/diff/help）
- `scripts/ccc-search.py` — 跨项目 `.ccc/` 关键词搜索
- `scripts/ccc-init.py` — 新项目初始化（AGENTS.md + .ccc/profile.md）
- `scripts/ccc-hook.sh` — Claude Code pre-tool hook（区分源码/元数据）
- `scripts/executor-watchdog.sh` — Executor 启动前健康检查
- `scripts/install-ccc-as-skill.sh` — 跨平台 skill 安装（Mavis/Claude Code/ZCode）
- `templates/AGENTS.md` + `templates/.ccc-profile.md` — 项目模板
- `cccq` alias（ccc status 的简写）
- `ccc status -w [N]` — 可配置间隔的 watch 模式

### Fixed
- CCC_HOME symlink 解析（realpath 替代 dirname）
- ccc status 内联实现（避免 cccq symlink 循环）
- ccc diff 不跳仓（用当前目录而非 CCC_HOME）
- ccc-hook.sh 绝对路径兼容（匹配 `*/.ccc/*`）
- cccq -w 参数丢失 bug（改为转发全部位置参数）
- `clear` 在无 TERM 环境触发 set -e 退出的问题

### Validated (Verifier 独立验证)
- 13/13 功能验收通过
- 5/5 adversarial probes 通过
- VERDICT: PASS

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

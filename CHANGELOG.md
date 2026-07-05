# Changelog

All notable changes to CCC (Codex Claude Collaboration) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2026-07-05

### Added
- `scripts/ccc-exec-commit.sh` — Executor 退出后自动 commit（替代 LLM 做机械操作）
- `ccc commit` 子命令 — 委托给 ccc-exec-commit.sh

### Changed
- **拆分 Executor commit 职责**（P0.2）：Executor 只做文件编辑，commit 由外部脚本自动处理
- `templates/executor-prompt.template.md` — 删除所有 git add/commit 指令，更新完成定义，自检从 6 项调为 5 项
- `CLAUDE.md` — Executor 启动标准新增 commit 调用步骤，C2 从 "commit-push" 缩为 "push"，新增兜底 commit 段落
- `references/red-lines.md` — C2 改为 push，新增"红线 8 Fallback"段允许 Planner 兜底 commit

### Fixed
- Executor 自检 4（commit hash 检查）移除——commit 由外部处理，自检不再校验
- Executor 自检 1（git status）改为确认无已暂存内容
- 示例 section 同步删除 commit 相关行

## [0.3.1] - 2026-07-04

### Added
- `scripts/ccc` — 统一 CLI 入口（status/search/init/diff/help）
- `scripts/ccc-search.py` — 跨项目 `.ccc/` 关键词搜索
- `scripts/ccc-init.py` — 新项目初始化（AGENTS.md + .ccc/profile.md）
- `scripts/ccc-hook.sh` — Claude Code pre-tool hook（区分源码/元数据）
- `scripts/executor-watchdog.sh` — Executor 启动前健康检查
- `scripts/install-ccc-as-skill.sh` — 跨平台 skill 安装（CCC / Claude Code / ZCode）
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
- mavis session new C6 = Critical (Lesson 19, 红线 8) — **v0.5 起改红线 9 表述**
- 默认预算 200 USD (5 USD 历史 bug 已修)
- 一个 phase 一个 commit (红线 4)
- phases.json 必写全 (红线 5)

## [0.2.x] - 2026-06-30 之前

### Internal Prototype
- 早期间脚本集阶段
- 多个项目实验性使用 (qx-observer / qb / xianyu)
- 形成 templates/ + skills/ + projects/ 雏形

---

## [0.5.0] - 2026-07-06 — Connect–Claude Code 重构

### Changed (BREAKING)

- **CCC 重新定位**：从 "Codex Claude Collaboration" framework 代码库 → **Connect–Claude Code SKILL 资产**
- **含义**：**C**onnect — **C**laude **C**ode（连接 Claude Code 能力到任意 IDE 工具）
- **SKILL.md**：重写为唯一 prompt 注入资产，244 行 → 169 行（精简）
- **README.md / CLAUDE.md**：重写，文档分层清晰（SKILL / README / CLAUDE / docs/）
- **与 qxo 解耦**：`projects/qxo/lessons.md` 迁移到 `docs/lessons.md`，CCC 不再绑任何项目

### Added

- `docs/roadmap.md`：v0.5 / v0.6 / v0.7 / v1.0 + 扩展阶段四阶段路线
- `docs/architecture.md`：v0.5 框架说明书（重写）
- `docs/lessons.md`：framework 级教训沉淀（从 projects/qxo/ 迁 1448 行）
- 红线 11：Verifier 必须写 verdict 文件（Lesson 28 配套）
- 红线 12：禁止 agent 自主启用 CCC（用户显式触发）
- Lesson 27：`claude -p` 是 print 模式，prompt 必须走 stdin（CCC 文档自洽修复）
- Lesson 28：口头 PASS 不算 PASS，verdict 必须有产物证据

### Fixed

- `references/adapters/runtime-claude-p.md`：`claude -p` 参数表从错误描述（"-p = prompt 参数"）改成正确描述（"print 模式开关 + stdin 喂内容"）
- `templates/executor-prompt.template.md`：文首加显眼警告 + 参数表重写
- `templates/report.report.md`：加 `> VERDICT:` 占位段为必填（红线 11 强制）

### Removed

- `projects/qxo/lessons.md`（迁至 docs/lessons.md，原始保留为 `.archived-2026-07-06`）
- 根 `AGENTS.md`（标记 DEPRECATED，已合并进 CLAUDE.md）
- v0.3.x 残留 framework-style 调用约定

### Migration

- v0.5 升级不需要任何代码改动 —— CCC 是 SKILL 资产，不存在 import
- 用户在 IDE 内**重新加载 CCC skill** 即可生效
- 已有 4 文件契约（plans/phases/reports/verdicts）路径保持不变

### Verification

```bash
# SKILL 注入验证
cat ~/program/CCC/SKILL.md | head -3
# 期望: SKILL frontmatter + "CCC — Connect–Claude Code" 标题

# 红旗线验证
grep -E '红线 (11|12)' ~/program/CCC/references/red-lines.md
# 期望: 2 行命中

# 框架文档完整
ls ~/program/CCC/docs/
# 期望: lessons.md / roadmap.md / architecture.md / plan-spec.md / verification-spec.md ...
```

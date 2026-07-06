# Changelog — CCC

All notable changes to CCC will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Repository**: `~/program/CCC/`
> **Skill name**: `ccc-protocol`
> **Framework total**: scripts + references + docs + templates (single .ccc/ artifact dir per project)

---

## [1.2.0] — 2026-07-06 — 流程跑通 (CCC v1.0 Closure)

**里程碑**:Planner → Executor → Verifier 三角色**完整流程**首次跑通,5+5 机器化门控闭环。

参见 `.ccc/plans/ccc-engineering-foundation.plan.md` §T1.1-T1.7 + `.ccc/plans/hello-ccc-demo-v2.plan.md`。

### Added
- **`.ccc/state.md`**: Planner 接力文件(红线 10 强制,Lesson 13 schema)
- **`scripts/ccc-precheck.sh`**: 5 项前置门控(状态/项目/计划/相位/看门狗)
- **`scripts/ccc-finish.sh`**: 5 项后置门控(报告/验收/引用/范围/相位闭环)
- **`tests/scripts/test_ccc_precheck_finish_smoke.py`**: 10 个 smoke test
- **`hello-ccc-demo-v2`**: 3 phase + 独立 Verifier session 完整闭环 demo
- **`scripts/ccc-status.sh`**: 4 文件契约健康检查 CLI(105 行)
- **`scripts/ccc-cost.sh`**: 单任务 cost summary CLI(85 行)
- **`tests/scripts/test_ccc_status_smoke.py`**: 3 个 status smoke test
- **`docs/E2E-DEMO.md`**: 完整跑通 trace 文档

### Changed
- **SKILL.md**: 新增 §Planner 启动顺序 + §强制 watchdog + §ccc commit 闭环
- **`templates/executor-prompt.template.md`**: 集成 ccc-precheck/finish + ccc commit 引用
- **`templates/AGENTS.md`**: agent config 路径 `~/.mavis/` → `~/.config/ccc/` (mavis 清理配套)
- **`scripts/ccc-finish.sh`**: 排除 `.claude/` 元数据(范围白名单)

### Verified
- `pytest tests/scripts/test_ccc_precheck_finish_smoke.py` → 10/10 PASS
- `bash scripts/ccc-precheck.sh . hello-ccc-demo-v2` → 7/7 PASS
- `bash scripts/ccc-finish.sh . hello-ccc-demo-v2` → 7/7 PASS(完整 4 文件契约)
- Verifier 独立 session: 4/4 probes PASS
- 3 phase 任务: ccc-task-id=hello-ccc-demo-v2 phase=1/2-3/final

### Red Lines Enforced (v1.2.0)
| 红线 | v1.2.0 机器化 |
|------|---------------|
| 7 启动顺序固定 | ccc-precheck Gate 1-3 |
| 9 Executor 卡死止损 | ccc-precheck Gate 5 = watchdog |
| 10 跨会话不隐式记忆 | ccc-precheck Gate 1 = state.md |
| 11 Verifier 必写文件 | ccc-finish Gate 2+3 |
| 4+8 单 phase 单 commit | ccc-finish Gate 5 + ccc commit 闭环 |
| 3 范围白名单 | ccc-finish Gate 4 |

---

## [1.1.0] — 2026-07-06 — Engineering Foundation

**里程碑**：v1.0 release gate open + 工程化补漏 + 移交准备。

参见 `.ccc/plans/ccc-engineering-foundation.plan.md` — 24 tasks / 4 phases。

### Added
- **T14**: `docs/handoff-checklist.md` — 12 项移交验收 checklist
- **T13**: `tests/scripts/test_cluster_bus_benchmark.py` — 100 node 压测 (1000 hb avg 0.83ms)
- **T11**: `tests/scripts/test_integration_business_flows.py` — 3 条端到端集成测试

### Changed
- VERSION 0.5.0 → 1.1.0
- `scripts/cluster-bus.py`: h11 协议, atomic checkpoint, `--port` 参数
- `tests/scripts/test_integration_business_flows.py`: fix bytes/str Python 3.14 compat

---

## [1.0.0] - 2026-07-06 — Automation Open

### Added (8 commits / 8 reports)

- **P0-1**: `scripts/cluster-bus.py` — FastAPI node registry + heartbeat (5 endpoint)
  - commit `6af9121` / report `p0-1-cluster-bus.report.md`
- **P0-2**: `scripts/ccc-dispatch.py` — task triple output (no auto-dispatch)
  - commit `fa0fa2e` / report `p0-2-ccc-dispatch.report.md`
- **P1-1**: `references/cluster-protocol.md` — 跨设备协议规范 (10 sections, 229 lines, mTLS design)
  - commit `376e2b9` / report `p1-1-cluster-protocol.report.md`
- **P1-2**: `tests/cluster/test-capability-required.py` — Red Line 18 enforcement (7 cases, 6 passed, 1 skipped)
  - commit `090e918` / report `p1-2-test-capability.report.md`
- **P2-1**: `examples/cluster/{m1,feiniu}.yaml` — node config templates
  - commit `e32d9df` / report `p2-1-yaml-examples.report.md`
- **P2-2**: `tools/cluster-doctor.sh` — 5-section cluster diagnostic
  - commit `a6ffc11` / report `p2-2-cluster-doctor.report.md`
- **P3-2**: dispatcher PoC end-to-end — 3 nodes registered, m1 picked (score 0.795)
  - commit `8a19431` / report `p3-2-dispatcher-poc.report.md`
- **Final**: v1.0 release summary report
  - commit `f522c34` / report `v1.0-automation-summary.report.md`

### Engineering Discipline (red lines)

- **红线 11** (verifier file): 8 reports, all ≥ 100 lines
- **红线 18** (capability default): tests prevent clawmed-ai v3.1 failure
- **红线 19** (independent verifier): applied in P1-1 protocol design
- **红线 20** (bash v3 portability): all scripts compliant
- **Lesson 28 + 29 + 30** from v0.5 P0: applied throughout

### Borrowed / Cited

- `clawmed-ai` Universal Worker v3.1 + T1.2 worker analysis (heartbeat 30s/90s)
- `agentmesh` 6 projects (TCP discovery + capability routing consensus)
- Anthropic 2026 mesh paper (motwani et al, communications-effective multi-agent)
- 老板 `~/.claude/CLAUDE.md` 工程纪律 + red lines 跨项目沉淀

---

## [0.5.0] - 2026-07-06 — Connect–Claude Code 重构

### BREAKING

- **CCC 重定位**: 从 "Codex Claude Collaboration framework 代码库" → "Connect–Claude Code SKILL 资产"
- **SKILL.md 重写**: 单一 prompt 注入资产，169 行
- **含义**: **C**onnect–**C**laude **C**ode（连接 Claude Code 能力到任意 IDE）
- **`projects/qxo/` 解耦**: lessons.md 迁到 `docs/lessons.md`
- **Mavis 术语替换** → ccc 统一命名

### Added

- `SKILL.md` (169 行, 唯一注入 prompt)
- `references/red-lines.md` 新增 红线 11 + 12
- `references/adapters/runtime-opencode.md` OpenCode adapter
- `references/red-lines.md` 10 + 2 完整红线
- `DESIGN-VALIDATION.md` 设计决策永久证据链 (234 行)
- `references/adapters/runtime-opencode.md` 适配 OpenCode runtime
- `docs/lessons.md` Lesson 27 (`claude -p` 语义) + Lesson 28 (verdict 强证据)
- `references/adapters/runtime-claude-p.md` v2 更新 — print 模式 + stdin 喂内容
- `CHANGELOG.md` (v0.3 占位版本)

### Fixed

- `runtime-claude-p.md`: 修复 `-p` 描述错误（Lesson 27）

### Removed

- v0.3.x 阶段 `projects/qxo/` 整个目录 → `.archived-2026-07-06/`
- v0.3.x `distribution-report.md` → archive
- v0.3.x `references/adapters/scheduler-mavis-cron.md` → archive

### Documentation

- 文档分层：
  - `SKILL.md` (agent 唯一入口)
  - `README.md` (用户入口)
  - `CLAUDE.md` (framework 总纲)
  - `DESIGN-VALIDATION.md` (证据链)
  - `references/red-lines.md` (工程纪律)
  - `docs/lessons.md` (教训沉淀)
  - `docs/architecture.md` (框架结构)
  - `docs/roadmap.md` (发展路线)

---

## [0.3.2] - 2026-07-05 — 实测沉淀 (9 个 task)

### Added

- `scripts/ccc` CLI 入口 (status / search / init / commit)
- `scripts/ccc-init.py` 项目初始化
- `scripts/ccc-search.py` 工件搜索
- `scripts/ccc-cost-report.sh` 成本估算
- `scripts/ccc-exec-commit.sh` 自动 commit 兜底
- `scripts/ccc-hook.sh` Claude Code pre-tool hook
- `scripts/install-ccc-as-skill.sh` 安装到 `~/.claude/skills/`

### Tasks Closed (9 个 task)

- `add-ccc-archive` (2026-07-04)
- `add-ccc-cost-report` (2026-07-04)
- `ccc-test-auto-claude-code` (v1-v4, 2026-07-04 ~ 07-05)
- `ccc-test-html-manual-paitongshu` (2026-07-04)
- `ccc-v0.3.1-infrastructure` (2026-07-04)
- `ccc-v0.3.2-cccq-status-ux` + R2 (2026-07-04)
- `fix-ccc-v031-bugs` (2026-07-04)
- `push-ccc-v0.3.1-to-origin` (2026-07-04)

### Engineering (v0.3 → v0.5)

- 9 个 task 沉淀成 9 个 phases.json + 9 个 reports + 4 个 verdicts
- 教训沉淀：Lessons 1-26 (~1300 行)
- 4 文件契约确立 (`plans/` / `phases.json` / `reports/` / `verdicts/`)
- 三角色纪律 (Planner / Executor / Verifier)

---

## [0.3.0] - 2026-07-01 — 三角色 + 4 文件契约

### Added

- **三角色**：Planner / Executor / Verifier 严格分离
- **4 文件契约**：`.ccc/{plans,phases,reports,verdicts}/`
- **第 9 红线**: Planner 越界 = Critical (C1-C6 子条款)
- **commit 兜底机制**: `ccc-exec-commit.sh` 自动检测 working tree → commit

### Roles

- **Planner (Mavis/MiniMax-M3)**: 写 plan.md + phases.json
- **Executor (Claude Code CLI)**: 自主执行 plan → 写 report.md
- **Verifier (Claude Code CLI)**: 独立 session → 写 verdict.md (≥ 50 行)

---

## [0.1.0] - 2026-06-30 — Internal Prototype

### Added

- 内部脚本集阶段
- 多个项目实验性使用 (qx-observer / qb / xianyu)
- 形成 `templates/` + `skills/` + `projects/` 雏形

### Structure

```
~/program/CCC/
├── SKILL.md
├── templates/
├── skills/
├── projects/
└── references/
```

---

## 借鉴来源 (Borrowed)

| 来源 | 提供价值 | 落地 |
|------|---------|------|
| `clawmed-ai` plans/universal-worker-v3.1.md | heartbeat 30s/90s 协议 | `cluster-bus.py` § v1.0 |
| `clawmed-ai` plans/T1.2_worker_analysis.md | 注册/选举/capability | `ccc-dispatch.py` |
| `clawmed-ai` reviews/universal-worker-v3.1-review.md | v3.1 失败教训（能力匹配被注释掉） | `tests/cluster/test-capability-required.py` |
| GitHub `agentmesh-*` 6 projects (2025-11) | TCP discovery + capability 共识 | `references/cluster-protocol.md` |
| Anthropic 2026 mesh paper (Motwani et al) | multi-phase coordination | `references/cluster-protocol.md` § 4 |
| clawmed-ai `.gitignore` 模式 (.ccc/ 豁免 plans/phases/reports) | 元数据 vs 工件分离 | `.gitignore` v0.5 |
| abc PoC `scripts/git-bundle-stream.sh` | 跨设备 git bundle 流程 | `examples/cluster/` 配置参考 |

---

## 设计决策（永久证据链）

详见 `DESIGN-VALIDATION.md`。已验证决策：
1. SKILL 资产 vs framework 代码库
2. JSONL phases.json vs nested object
3. 三角色严格分离（Planner / Executor / Verifier）
4. 4 文件契约 + 红线 4/5/11
5. Capability-tag dispatch
6. bash v3 portability (Lesson 29)
7. 独立 Verifier session 工程价值 (Lesson 30)

---

## 已知限制 / Backlog

- ❌ **mTLS 待实现**：`cluster-bus.py` 当前 plaintext (P1-1 协议设计完成, 实现待 v1.1)
- ❌ **chunk_id 幂等性**：commit message 应含 `ccc-task-id=<id>` (红线 15 待实装)
- ❌ **真 Mac2017 bus**：当前用 `mac2017-fake` 模拟
- ❌ **自动派单**：dispatcher 仍需人工 stdin 'yes'
- ❌ **跨 IDE SKILL 实测矩阵**：Trae 验证过，Cursor / Zed 待测
- ❌ **CI**：GitHub Actions 模板存在但未实测 GFW 下 push

---

## 相关文件

- `README.md` — 30 秒上手
- `SKILL.md` — 注入 prompt (agent 唯一入口)
- `CLAUDE.md` — 框架总纲
- `DESIGN-VALIDATION.md` — 设计决策永久证据链
- `references/red-lines.md` — 13 条硬约束
- `docs/roadmap.md` — 发展路线图
- `docs/lessons.md` — 30 条工程教训
- `docs/architecture.md` — 框架结构
- `.ccc/plans/` — 所有 task plan.md
- `.ccc/reports/` — 所有 task report.md
- `.ccc/phases/` — 所有 task phases.json
- `.ccc/verdicts/` — 所有 task verdict.md

---

**Latest**: `bf88077` docs(ccc): T14 handoff-checklist.md (2026-07-06)
**Active branch**: main
**Version**: 1.1.0 (engineering foundation)
**Status**: v1.1 release — 24 tasks (T1-T14 done, T15+ pending Trae IDE)

[Unreleased]: https://github.com/hanrry2323/CCC/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/hanrry2323/CCC/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/hanrry2323/CCC/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/hanrry2323/CCC/releases/tag/v0.5.0

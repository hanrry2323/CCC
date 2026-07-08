# Changelog — CCC

All notable changes to CCC will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Repository**: `~/program/CCC/`
> **Skill name**: `ccc-protocol`
> **Framework total**: scripts + references + docs + templates (single .ccc/ artifact dir per project)

---

## [v0.21.0] — 2026-07-09 — 门控修补

### 新增
- `reviewer_role` 重写：调 Claude API 审查 `git diff HEAD~1` + plan `## 验收清单`
- `tester_role` 强制 baseline：检测 pyproject.toml 时追加 `pytest tests/ -q --cov=src --cov-fail-under=80`
- `_get_git_diff()` / `_review_with_llm()` / `_py_compile_fallback()` 辅助函数
- LLM 审查失败时 fallback 到 py_compile 静态检查

### 重构
- plan 模板加 `## 验收清单` 段
- `skills/ccc-reviewer/SKILL.md` 重写：5 大类审查清单 + 三级严重度
- `references/red-lines.md`：加 X7（reviewer 必须 LLM）

## [v0.22.0] — 2026-07-09 — audit 角色 + daily-auto-scan 收纳

### 新增
- `audit_role()` 新角色：全项目扫描 + AI 分类 + auto 直接修 / review 投 backlog
- `_audit_recent_commits` / `_audit_lint` / `_audit_classify` / `_audit_post_backlog` / `_audit_write_report` 辅助
- engine 主循环加 `_audit_should_run()` 时间检查（每 2h）

### 重构
- `FileBoardStore` 白名单 `backlog → planned` 允许（audit 投出直接到 planned）
- 报表路径：`{workspace}/.ccc/audit-reports/`（替代 `~/Desktop/auto-scans/`）
- lint baselines 迁到 `~/.ccc/lint_baselines/`

### 清理（v0.22 重点）
- 删除 `~/.claude/skills/daily-auto-scan/`（功能并入 audit_role）
- 删除 `~/.claude/scheduled_tasks.json` 中 cron `7 */2 * * *`（改 engine 触发）
- Memory 文件加迁移说明（链接到 CCC）

### 红线
- X8：audit 角色必须 2h 内只跑一次

---

## [v0.20.1] — 2026-07-08 — 串行执行引擎

> `ccc-engine.py` 替代 7 角色 launchd 定时轮询。
> 有任务即串行执行全链路，无任务休眠。

### 新增
- `scripts/ccc-engine.py` — CC Engine 串行执行守护进程（~280 行）
- `scripts/ccc-engine.sh` — Engine launchd 入口
- `scripts/uninstall-ccc-roles.sh` — 卸载旧 7 角色 plist
- `scripts/ccc-board.py`: 新增 `dev_role_launch()` + `dev_role_check_complete()` 引擎辅助函数
- `scripts/_config.py`: 新增 `engine_poll_interval` / `engine_idle_sleep` 配置项

### 重构
- `scripts/install-ccc-roles.sh`: 改为只装 Engine + board-server plist，支持 `--upgrade` 自动卸载旧角色
- `references/red-lines.md`: X5（7 plist 必装→Engine+board-server）、X6（角色频率→取消定时）
- `CLAUDE.md`: 架构文档更新到 v0.20.1
- `docs/roadmap.md`: 添加 v0.20.1 规划

### 删除（保留向后兼容）
- `scripts/roles/*.sh` 7 文件标记为 deprecated（不再由 launchd 触发，手动调用仍可用）
- 旧 launchd plist 14 个（CCC 7 + qxo 7），替换为每个 workspace 1 个 engine plist

### 验证
- pytest: 49 passed (同 v0.20.0)
- engine 启动正常，写 `.ccc/engine-heartbeat.json`
- compile: 全部 Python 文件无语法错误

---

## [v0.20.0] — 2026-07-08 — Dev 体验 + 运维完备

### 新增
- ops 角色扩展: launchd 7 角色自检 + `.ccc/metrics.json` 指标收集
- 日志清理: ops 角色自动删除 >30 天的 role-*.log
- E2E 覆盖: 白名单外语法错误跳过 + 白名单内语法错误拒绝 (7→9 步)

### 重构
- `scripts/ccc-board.py` ops_role: 新增 launchd 自检、日志清理、metrics 收集
- `scripts/ccc-board.py`: docstring v0.18 → v0.20
- `scripts/ccc-board-server.py`: docstring v0.18 → v0.20
- `VERSION`: v0.19.0 → v0.20.0

### 修复 (v0.19 对抗性审查 6 项)
- S1: `opencode-pool.py` asyncio 阻塞 — 改为 `run_in_executor` 包装
- S2: `ccc-exec-launcher.sh` 重试日志覆盖 — 文件名加 `-attempt-${attempt}` 后缀
- W1: `_board_store.py` list_tasks 无读锁 — 加 `LOCK_SH` 共享读锁
- W2: `ccc-board.py` schema_version 字符串匹配 — 改用 `json.loads` 检测 (第一处)
- N1: `_executor.py` 代码重复 — 提取模块级 `resolve_opencode()` 函数
- N5: `board-task-schema.md` 文档不一致 — 修正为 phases.json 格式章节

### 修复 (v0.20 对抗性审查 4 项)
- S3: `ccc-board.py` schema_version 第二处仍用 `startswith` — 改为 `json.loads` 检测
- S4: `opencode-exec.py` 未复用 _executor — 改为 `from _executor import resolve_opencode`
- W5: ops_role 函数内 `import json as _json` 冗余 — 删除，用文件顶部 `json`
- W6: ops 角色 launchctl 自检未检查 returncode — 加 `r.returncode == 0`

### 文档
- docstring 版本号 `scripts/ccc-board.py`: v0.18 → v0.20
- docstring 版本号 `scripts/ccc-board-server.py`: v0.18 → v0.20
- `board-task-schema.md`: 新增 phases.json 格式章节

## [v0.19.0] — 2026-07-08 — 基础加固 + 扩展通路

### 新增
- `scripts/_config.py`: 集中配置 Config dataclass，消灭散布的硬编码
- `scripts/_board_store.py`: BoardStore 抽象 + FileBoardStore 实现（含 fcntl.flock 锁 + 原子写入）
- `scripts/_executor.py`: Executor 协议 + OpenCodeExecutor 实现
- `references/board-task-schema.md`: task JSONL 格式标准（CCC-QXO 共享契约）
- `tests/e2e/test_pipeline_smoke.sh`: 完整流水线 E2E 集成测试

### 重构
- `scripts/ccc-board.py`: 存储操作委托 FileBoardStore，角色业务逻辑与存储层解耦
- `scripts/ccc-board-server.py`: 消除 list_tasks/move_task/create_task 重复代码，导入 FileBoardStore
- `scripts/opencode-pool.py`: 消除 importlib hack，导入 OpenCodeExecutor
- `scripts/ccc-exec-launcher.sh`: 新增 3 次重试（指数退避 60/120/240s）

### 文档
- `docs/roadmap.md`: 新增 v0.19/v0.20 规划、三层架构图、与 QXO 独立发展说明
- `docs/architecture.md`: 重写为三层架构（L3 角色 → L2 抽象 → L1 实现）
- `CLAUDE.md`: 资产清单更新、QXO 关系改为"独立发展共享契约"

### 修复
- phases.json 写入带 `"schema_version": "1.0"` 元数据行
- dev_role 读取 phases 时跳过 schema_version 行
- 看板写操作加文件锁防 race condition

## [Unreleased] — v0.8 — OpenCode CLI 执行端重构

**里程碑**：CCC 执行器从 claude CLI 切到 **OpenCode CLI**（CLI 模式，禁用 HTTP/serve），新增 3 条 OpenCode 进程管理红线（X1/X2/X3）。

### Added
- `scripts/opencode-exec.py` — OpenCode CLI 执行器（asyncio 子进程 + 必杀兜底 + pid 文件）
- `scripts/opencode-pool.py` — 进程池（asyncio.Semaphore(3) 硬限，红线 X1）
- `scripts/opencode-watchdog.sh` — 残留扫描（pid 文件 + pgrep 兜底，红线 X2/X3）
- `scripts/ccc-notify.sh` — macOS 桌面通知（L1/L2/L3）
- `scripts/ccc-hook.sh` — 通用钩子（pre-exec / post-exec / on-error / pre-commit）
- 红线 X1（OpenCode 进程池最多 3 并发）
- 红线 X2（每 phase 必杀 opencode 进程）
- 红线 X3（OpenCode 启动前必跑残留 watchdog）
- `tests/scripts/test_opencode_pool_max_parallel.py` — 验 X1
- `tests/scripts/test_opencode_pool_kill_residual.py` — 验 X2
- `tests/scripts/test_opencode_watchdog_cleanup.py` — 验 X3

### Changed
- `scripts/ccc-exec-launcher.sh` — 从 tmux+claude 改为 opencode CLI 串联
- `references/adapters/runtime-opencode.md` — 重写为执行器契约（CLI 模式，弃用 4096 serve）
- `SKILL.md` / `CLAUDE.md` / `README.md` — 资产清单 + 红线表同步更新

### Removed
- `DESIGN-VALIDATION.md`（v0.7 历史 design review）
- `examples/cluster/` `examples/scheduler/` `examples/qxo-audit-frontend.md`（旧路线预留）
- `scripts/ccc-monitor.sh` `scripts/executor-watchdog.sh` `scripts/install-ccc-as-skill.sh`（旧 monitor/watchdog/installer）
- `scripts/*.md` 副本（每个脚本旁的重复文档）
- `tests/scripts/test_executor_watchdog_smoke.py`（旧 watchdog 已删）
- 卸载 `com.opencode.serve` launchd 守护（v0.8 不用 HTTP）

### Verified
- pytest: 57 passed, 0 failed in 10.73s
- smoke test: 10 项能力 9 项直接通过，1 项模型 provider（v0.9a 修复）
- launchd 调度: load → start → 告警落文件 → unload 全链路通

---

## [Unreleased] — v0.9a — model provider 修复 + v0.9b/c 决策

**里程碑**：v0.9a 修复 opencode 调模型失败（`--model flash` → `--model loop/flash`），跑通真实模型调用。v0.9b 飞轮和 v0.9c 收尾按用户节奏。

### Fixed
- `scripts/opencode-exec.py` — `--model flash` → `--model loop/flash`（v0.9a 实测修复）
- `references/adapters/runtime-opencode.md` §六 — 模型映射段更新（对外 flash / 内部 loop/flash）
- `docs/lessons.md` — 追加 Lesson 32（opencode 模型名必须带 provider 前缀）

### Verified
- 真实模型调用: `opencode run --model loop/flash` exit 0，52s 返回
- pytest: 57 passed
- 中转站: localhost:4002（loop provider）确认工作

---

## [Unreleased] — v0.11 消化 — 范式转变标记

**里程碑**：v0.11 完结后消化，标记 CCC 范式转变 = "opencode 写 + 人工 review"。

### Added
- `docs/lessons.md` Lesson 34 — opencode run 起 node 孙子进程，killpg 在 macOS 不可靠
- `docs/lessons.md` Lesson 35 — opencode 写代码质量超过 v0.7 时代人工基线
- `docs/roadmap.md` 范式转变段（v0.11 起默认 opencode 写）

### Verified
- install-ccc-scheduler install/uninstall 闭环烟测：plist 生成 + plutil lint OK + 卸载干净
- 远端 5 tag 完整：v0.7.0 / v0.8.0 / v0.9.0 / v0.10.0 / v0.11.0

---

## [Unreleased] — v0.12 — bug fix sweep

**里程碑**：v0.12 全量扫 bug（7 个发现，3 真 bug 修，4 复查非 bug 加注释）。3 类修复模式：数据泄漏 / 静默失败 / 配置硬编码。

### Fixed
- **Bug 1+3**: `opencode-exec.py` 长 prompt 临时文件永久泄漏（磁盘 + 隐私）— finally 块 unlink
- **Bug 2**: `ccc-finish.sh` bare `except: pass` 吞所有异常 — 改 `except json.JSONDecodeError as e` + stderr 输出
- **Bug 6**: `ccc-hook.sh` timeout=30 写死 — 加 `CCC_HOOK_TIMEOUT` env + macOS perl alarm 兜底

### Verified (非 bug, 加注释说明)
- **Bug 4**: watchdog `for pf in *.pid` 空目录不进 loop（bash 默认行为）
- **Bug 5**: ccc-precheck `open(fp)` 没指定 encoding（macOS UTF-8 默认）
- **Bug 7**: launcher log 命名已含 phase_id，并发不交错

### Added
- `tests/scripts/test_bug_fixes_v012.py` — 3 个 test 覆盖
- `docs/lessons.md` Lesson 36 — bug 分类 + 修复模式

### Verified
- pytest: 69 passed (66 + 3 新增)
- 远端 6 tag: v0.7.0 / v0.8.0 / v0.9.0 / v0.10.0 / v0.11.0 / v0.12.0

---

## [Unreleased] — v0.11 — 开箱即用调度 + 队列真测试

**里程碑**：v0.11 落地 a（钩子模板 + scheduler 安装器）+ b（队列 N phase 真测试）+ b-fix（红线 X2 必杀修）。v0.11 完结后，CCC 具备了从"用户启 launcher" → "launchd 周期调 launcher" → "队列跑多 phase" 的全链路。

### Added
- `templates/hooks/post-exec.sh` — phase 完成自动 git add+commit
- `templates/hooks/on-error.sh` — phase 失败 L2 通知 + 落 abnormal report
- `templates/hooks/pre-commit.sh` — soft lint (TODO/print/debugger)
- `scripts/install-ccc-scheduler.sh` — install/uninstall/status/--dry-run 一键装 launchd
- `tests/scripts/test_queue_e2e_3phase_pass.py` — 3 phase 全成功
- `tests/scripts/test_queue_e2e_mid_fail.py` — 中间失败 pause
- `tests/scripts/test_queue_e2e_resume.py` — pause 后续跑
- `docs/lessons.md` Lesson 33 — opencode run positionals 截断 200 字符

### Changed
- `scripts/opencode-exec.py` — 长 prompt 走 --file 协议（positionals 截断修复）
- `scripts/opencode-exec.py` — `start_new_session=True` + `os.killpg`（kill 级联）
- `scripts/opencode-watchdog.sh` — 扫 `opencode (run|exec)` + pkill -f 兜底
- `scripts/ccc-queue.sh` — `CCC_LAUNCHER_OVERRIDE` env var 支持（mock 测试）

### Fixed
- **红线 X2 失守修复**：launcher 杀 opencode 不级联到孙子 node 进程（macOS killpg 不可靠）
  - 修法 1: opencode-exec 用 killpg
  - 修法 2: watchdog 加 pkill -f 兜底

### Verified
- pytest: 66 passed (63 + 3 新增)
- 真实模型调用: 11.9s 返 exit 0
- launchd 调度: 装/卸/触发全通
- 队列 3 场景: pass / mid_fail(exit 5) / resume 全验
- 必杀: 30s sleep + 2s timeout 必杀

---

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

## [v0.7-slim] — 2026-07-07 — 精简 80→15 (slim route closure)

**里程碑**:CCC 从 80+ 文件瘦身到 15 个核心文件。砍掉为"路线预留"而存在的过度工程化代码。

参见 `.ccc/plans/v0.7-slim.plan.md` + `.ccc/reports/v0.7-slim.report.md` + `docs/lessons.md` Lesson 29。

### Removed
- **cluster 总线整套** (phase 1):`scripts/cluster-bus.py` + `ccc-znode-register.py` + `ccc-zcode-bridge.sh` + `ccc-zcode-orchestrate.sh` + `tools/cluster-doctor.sh` + `references/cluster-protocol.md` + `tests/cluster/`
- **多 IDE 适配器整套** (phase 2):`references/adapters/runtime-{cursor,claude-p,zcode,claude-code}.md` + `scheduler-{launchd,github-actions}.md` (保留 `runtime-opencode.md`)
- **派单/飞轮/成本/precommit** (phase 3):`scripts/ccc-dispatch.py` + `ccc-hook.sh` + `ccc-scheduler.sh` + `hello-ccc.sh` + `flywheel-scan.py` + `ccc-cost-report.sh` + `ccc-cost.sh` + `precommit-{bash-quality,verdict-length}.sh` + `.ccc/dispatches/` + 9 测试
- **worktree 副本** (phase 4):`.claude/worktrees/oral-calc-commit/`

### Changed
- **CLAUDE.md**:精简"工程纪律配套扩展"段
- **README.md**:精简"配套"段 + 删除 ZCode Adapter 整段
- **.ccc/profile.md**:精简"关键资产清单"表(8 脚本 + 8 测试)
- **.ccc/state.md**:追加"v0.7-slim 精简决策"到关键历史决策
- **scripts/ccc**:删除 `run` 子命令(ccc-zcode-orchestrate.sh 已删)
- **scripts/ccc-exec-commit.sh** + 测试:历史任务名 "cluster-bus-bugfixes" → "historical task phase 1"

### Added
- **docs/lessons.md** Lesson 29:路线图当现实做 = 过度工程化
- **references/red-lines.md** 红线 13 (v0.7-slim 配套):禁止未使用路线代码
- **.ccc/reports/v0.7-slim.report.md**:执行报告 + 验收证据

### Test
- **精简前**:21/21 smoke tests PASS(测的是被删功能)
- **精简后**:42/42 smoke tests PASS(测的是保留功能)

## [v0.7a] — 2026-07-07 — 修 plan 阈值 + 清理 qxo 归档

**里程碑**:修正 v0.7-slim plan 拍脑袋写的"60-80 文件"验收数字为按 sections 实绩对照;删除 qxo 归档(已解耦)。

参见 `.ccc/plans/v0.7a.plan.md` + `.ccc/reports/v0.7a.report.md` + `docs/lessons.md` Lesson 30。

### Changed
- **`.ccc/plans/v0.7-slim.plan.md`**:改动 4 验收段 + 全局验收清单:"60-80 文件" → "scripts/ 30+ → 8、tests/ 21 → 8、adapters/ 7 → 1" 实绩对照(原数字已废除,标注为 Planner 拍脑袋)

### Added
- **`docs/lessons.md` Lesson 30**:不要拍脑袋写验收数字(可执行规则 = sections 分项对照,避免单一全局数字)
- **`.archived-2026-07-06/README.md`**:归档边界说明(CCC v0.7 起不再维护,删子目录需先 grep CLAUDE.md)

### Removed
- **`.archived-2026-07-06/qxo-project/`**:qxo 已与 CCC v0.5 解耦(CLAUDE.md 明文),删除整个归档子目录(保留 `.archived-2026-07-06/` 目录本身)

## [v0.7d-prime] — 2026-07-07 — 红线 14+15 工程化 (monitor + 5min 轮询)

**里程碑**:把"自动开 monitor + 5 分钟轮询 + 完成自动终止"沉淀为 CCC 工具链。未来所有 Executor 任务通过 `ccc-exec-launcher.sh` 一键起 monitor + Executor + poll 三件套。

参见 `.ccc/plans/v0.7d-prime.plan.md` + `.ccc/reports/v0.7d-prime.report.md`。

### Added
- **`scripts/ccc-monitor.sh`**:幂等开 tmux monitor 窗口(已存在则跳过,避免重复开窗)
- **`scripts/ccc-poll.sh`**:5 分钟轮询指定窗口 + 完成信号检测(`❯` prompt + 无 `esc to interrupt`)+ 自动 `break` 退出
- **`scripts/ccc-exec-launcher.sh`**:三件套整合(开 monitor → send-keys 触发 Executor → 后台 nohup 启动 poll,PID 写入 `/tmp/poll-<WINDOW>.pid`)
- **`references/red-lines.md` 红线 14 + 红线 15**:Executor 必须配 monitor + 5min 轮询 / 轮询进程完成自动终止
- **`docs/engineer-flow.md`**:串行 vs 并行投递模式 + ccc-exec-launcher.sh 三件套用法 + 失败兜底(poll 异常退出)

---

## [v0.7.0] — 2026-07-07 — v0.7 任务链完结 (umbrella release)

**里程碑**:CCC v0.7 整条任务链(slim → a → b → c → d → d-prime → e → e-fix → f)统一收束为 `v0.7.0` release。从 v1.2.0 流程层版本号**回落**到 v0.7.0 —— 因为流程层 v1.0 已闭环,而代码层经过 slim 精简后,只配 v0.7.0 的能力级别。后续 v0.8 起重新自增代码版本。

参见 `.ccc/plans/v0.7f.plan.md` + `.ccc/reports/v0.7f.report.md`。

### Sub-task 收录(sections 分项)

| 子任务 | 主题 | 关键产出 | 教训 |
|--------|------|---------|------|
| **v0.7-slim** | 精简 80→15 | scripts 30+ → 8、tests 21 → 7、adapters 7 → 1 | Lesson 29 |
| **v0.7a** | 修 plan 阈值 + 删 qxo 归档 | sections 分项实绩对照 + qxo 子目录删 | Lesson 30 |
| **v0.7b** | 3 处文档统一资产清单 | SKILL.md / README.md / state.md 资产表一致 | — |
| **v0.7c** | 5 命令验收通过 | 8 脚本(实 12,见 Lesson 31) | Lesson 31 |
| **v0.7d** | 4 窗口 cwd 对齐 | 全部相对 CCC repo root | — |
| **v0.7d-prime** | monitor + poll + launcher 工具化 | 红线 14 + 15 + 三件套 | — |
| **v0.7e** | Verifier CONDITIONAL_PASS | 独立 session 验证通过 | — |
| **v0.7e-fix** | SKILL.md L218-222 hotfix | 删过时的 planner 启动顺序引用 | — |

### Files Touched (sections 分项,各子任务汇总)

| Section | 数量 | 备注 |
|---------|------|------|
| `VERSION` | 1 | 1.2.0 → v0.7.0 |
| `CHANGELOG.md` | 1 | 本文件 + v0.7 各子任务段已存在 |
| `.ccc/state.md` | 1 | 接力索引更新 |
| `docs/lessons.md` | 1 | 追加 Lesson 31 + 32 |
| `.ccc/reports/v0.7f.report.md` | 1(新增) | 本次执行报告 |
| `.ccc/phases/*.json` | 1 | 更新 phases.json |
| `SKILL.md` / `references/red-lines.md` / `scripts/` | **0** | **禁止改**(红线 13 + 14 + 15) |

### Red Lines Enforced (v0.7.0)
| 红线 | v0.7.0 触发 |
|------|------------|
| 13 禁止未使用路线代码 | v0.7-slim 删 cluster-bus / dispatch / flywheel |
| 14 Executor 必配 monitor + 5min 轮询 | v0.7d-prime 三件套 |
| 15 轮询进程完成自动终止 | v0.7d-prime `ccc-poll.sh` break 检测 |

---

## [v0.7.0-closure] — 2026-07-07 — 收尾完成,等待 tag + push

**里程碑**:v0.7.0 收尾。V0.8 加固(窗口识别/空闲选择/冲突拦截/完成回写 + 红线 16 + 3 pytest)因 Claude 在 fake tmux 调试卡 32m+,被用户叫停 → 半成品全部迁出到 worktree `../CCC-v0.8-wip`(branch `v0.8-wip`),main 干净。

**8 个 verdict 全部 PASS / CONDITIONAL_PASS**:v0.7-slim + v0.7a/b/c/d/d-prime/e-fix/f(独立 Verifier session 写 verdict.md,≥3 probes,红线 11)。

**主干验收**:42 pytest passed(`pytest tests/ -q --ignore=...v0.8 untracked`)。V0.8 新加 3 测试留在 worktree,不阻塞 v0.7.0。

**Tag + push 清单(待用户执行)**:
```bash
cd /Users/apple/program/CCC
git tag -a v0.7.0 -m "v0.7.0 umbrella release: slim + a/b/c/d/d-prime/e/e-fix/f"
git push origin main --tags
```

**为什么 V0.8 不进 v0.7.0**:
- V0.8 是**加固**(新增能力),不是 v0.7 的修复
- V0.8 半成品含未验证代码(3 个 fail pytest + 未跑通的手动调试)
- 独立版本号 `v0.8.0` 更清晰,review 也更干净

---

## [Unreleased] — v0.18 — 6 角色独立 SKILL + 知识库监理逻辑

**里程碑**：每个角色拥有独立 SKILL.md（职责/方法论/红线/知识库注入），参考 `agent-teams.md` + `practitioner-insights.md` 等行业最佳实践。

### Added
- `skills/ccc-product/SKILL.md` — 产品经理 skill + **SPEC 门禁**
- `skills/ccc-dev/SKILL.md` — 开发工程师 skill + **steer don't launch-and-forget** + 迭代检索
- `skills/ccc-reviewer/SKILL.md` — 代码审查员 skill + **只读不写** + **1:4 比例**
- `skills/ccc-tester/SKILL.md` — 测试工程师 skill + **双门禁验证**（pytest + plan 验收逐条）
- `skills/ccc-ops/SKILL.md` — 运维工程师 skill + **告警升级链 L1/L2/L3**
- `skills/ccc-kb/SKILL.md` — 知识管理员 skill + **AGENTS.md 最终收集**
- `skills/README.md` — skill 索引（6 角色 + 2 遗留角色）
- `templates/pending-agents-suggestions.md` — kb 收集 AGENTS.md 建议的模板

### Changed
- `scripts/roles/{product,dev,reviewer,tester,ops,kb}.sh` — 启动时加载对应 SKILL.md（export CCC_ROLE + CCC_ROLE_SKILL）, 记录 skill frontmatter 到 log

### Knowledge Base Injected
- **SPEC 门禁**（`agent-teams.md:1923`）：product 拆 subtask 必须过 Specific/Programmatically evaluable/Explicit scope/Constrained
- **Steer don't launch-and-forget**（`practitioner-insights.md:229`）：dev 的监督姿态
- **Reviewer 只读不写**（`agent-teams.md:1186`）：有写权限就会去修，产生 merge conflict
- **1 reviewer per 3-4 builders**（`agent-teams.md:1184`）：reviewer 积压监控
- **AGENTS.md 积累**（`agent-teams.md:1040-1063`）：沉淀跨 session 工程教训，禁止 agent 直接写入

### Verified
- 6 角色 shell 脚本语法通过（`bash -n`）
- `ccc-board.py index` 正常返回
- ops 角色端到端运行验证（加载 skill → 调 board.py → 退出 0）

---

## [Unreleased] — v0.17 — 战略地图 + 文档体系对齐 6 角色

**里程碑**：v0.16 6 角色系统落地后, 沉淀战略地图, 所有 cloud agent 启动第一件事读 STRATEGY-MAP.md。

### Added
- `docs/STRATEGY-MAP.md` — 战略地图（启动必读第一份）
  - 10 段: CCC 是什么 / 范式演进史 / 6 角色系统 / 看板 / 完整调用链 / 红线 / 自动化 / 模型路由 / 教训 / 怎么用
- `SKILL.md` — 加"启动必读战略地图"段（红线 7 升级）
- `CLAUDE.md` — 6 角色矩阵（替换 3 角色旧路由）
- `references/red-lines.md` — X4/X5/X6 三条新红线（v0.16 配套）
  - X4: 每 phase 必走看板流转
  - X5: 6 角色 plist 必装
  - X6: 角色频率不许改
- `docs/roadmap.md` — 5 次范式转变标注（v0.11 / v0.12 / v0.15 / v0.16 / v0.17）

### Changed
- SKILL.md version: v1.1 → v1.6
- 编号索引表加 X4/X5/X6 三行

### Verified
- 启动必读链验证: STRATEGY-MAP.md → red-lines.md → lessons.md → state.md
- 6 plist 装上 + 频率正确
- 9 tag 完整: v0.7.0 → v0.16.0

---

## [Unreleased] — v0.16 — 6 角色定时开发系统 + 任务看板

**里程碑**：CCC 从 3 角色扩到 6 角色定时开发系统。任务在 6 列看板流转, 6 launchd plist 周期跑。

### Added
- `.ccc/board/` 6 列任务看板 (backlog/planned/in_progress/testing/verified/released)
- `scripts/ccc-board.py` 6 角色核心
- `scripts/roles/{product,dev,reviewer,tester,ops,kb}.sh` × 6
- `scripts/install-ccc-roles.sh` 一键装 6 plist

### Verified
- 6 plist 装上, launchctl list 6 行
- 看板 e2e: backlog→planned→in_progress→testing→verified→released
- pytest: 69 passed


## [v0.18.0] - 2026-07-07

- feat-agents-approve: AGENTS.md 审批流程 看板发布

## [v0.18.0] - 2026-07-08

- feat-regress-notify: [ABNORMAL] 回测失败通知：regress 发现回归时，除了建 bug 还要发桌面通知（ccc-notify.sh） 看板发布

## [v0.18.0] - 2026-07-08

- feat-product-auto: product 自动调 Claude API 写 plan（--promote 已实现，需测试中转站连通性） 看板发布

## [v0.18.0] - 2026-07-08

- feat-role-bar: 前端角色状态栏对接 /api/roles，实时显示 7 角色最新执行状态（ok/fail/idle+执行时间） 看板发布

## [v0.18.0] - 2026-07-08

- feat-card-detail: [ABNORMAL] 前端卡片点击弹出详情面板，显示任务完整信息（题目/描述/当前列/move事件列表） 看板发布

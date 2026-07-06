# CCC Engineering Foundation Plan

> 目标：把 CCC 从"自研脚本集合"升级为"工程化软件项目"，达到可移交门槛，让 Trae + CCC skill 接管开发。
> 起讫日期：2026-07-06 起
> 工作量：~43h 实际开发 + 持续监督
> 角色分工：Claude (执行) / 老板 (总指挥，非紧急不打断)

---

## 范围

- **目标**：
  1. CCC 项目达到工程化软件项目标准（文档 / 测试 / CI / pre-commit 都有）
  2. 为可移交做准备：Trae + CCC skill 能自举开发 CCC
  3. 我从"开发者"转为"总指挥 / reviewer"
- **只改文件**：
  - `/Users/apple/program/CCC/` 内部所有文件
  - 不新增平台依赖
- **不改文件**：archive 目录 (`.archived-2026-07-06/`)，v0.3 历史 `.ccc/plans/*.plan.md`（仅追加新 .md）
- **执行方式**：auto
- **Phase 数**：4 阶段共 24 个 task

---

## 改动总览

### 阶段 1: 工程化补漏（4 个工作日）

| Task | 工作量 | 交付物 | 文件位置 |
|------|--------|--------|----------|
| T1. 写 CHANGELOG.md (v0.1→v0.5→v1.0) | 1h | 1 文件 | `CHANGELOG.md` (重写) |
| T2. 写 scripts/<name>.md for 11 scripts | 4h | 11 文件 | `scripts/<name>.md` |
| T3. 写 smoke test for 11 scripts | 4h | 11 测试 | `tests/scripts/test_<name>.py` |
| T4. DESIGN-VALIDATION.md v1.0 段回填 | 1h | 1 段落 | `DESIGN-VALIDATION.md` |
| T5. docs/USAGE.md | 2h | 1 文件 | `docs/USAGE.md` |
| T6. docs/CONTRIBUTING.md | 2h | 1 文件 | `docs/CONTRIBUTING.md` |
| T7. docs/GLOSSARY.md | 1h | 1 文件 | `docs/GLOSSARY.md` |
| T8. docs/TROUBLESHOOTING.md | 2h | 1 文件 | `docs/TROUBLESHOOTING.md` |
| T9. pre-commit hooks | 2h | 1 文件 | `.pre-commit-config.yaml` |
| T10. CI GitHub Actions | 2h | 1 文件 | `.github/workflows/ci.yml` |

**小计：~19h**

### 阶段 2: 测试覆盖率补齐（2 个工作日）

| Task | 工作量 |
|------|--------|
| T11. pytest 全 scripts 覆盖（unit + integration） | 6h |
| T12. E2E test：`ccc full 跑` 真集成 Trae | 4h |
| T13. cluster-bus 100 node 压测 | 2h |

**小计：~12h**

### 阶段 3: 移交准备 + v1.1（1 个工作日）

| Task | 工作量 |
|------|--------|
| T14. handoff-checklist.md（12 项打勾） | 2h |
| T15. Trae 真加载 CCC skill 跑 3 个不同任务 | 2h |
| T16. 产出"可移交报告"（我 → 你）| 1h |
| T17. CCC version bump v1.0 → v1.1 | 1h |

**小计：~6h**

### 阶段 4: 移交 + 持续监督（持续）

| Task | 工作量 |
|------|--------|
| T18. CCC dev workflow 文档化 | 2h |
| T19. 训练 Trae 3 真开发任务 | 6h |
| T20. 持续监督 / review / validation | 持续 |

**小计：6h + 持续**

---

## 改动细节（按 task 拆分）

### T1: CHANGELOG.md

### 做什么
完整版本历史 + 决策 + 借鉴来源。当前文件是占位空模板，需重写。

### 怎么做
- 章节：
  - v0.1.0 (2026-06-30) - 内部脚本阶段
  - v0.3.0 (2026-07-01) - 三角色分离 + 4 文件契约
  - v0.3.2 (2026-07-05) - 9 个 task 沉淀
  - v0.5.0 (2026-07-06) - **Connect–Claude Code** 重构
  - v0.5 P0 (2026-07-06) - Lesson 29/30 + flywheel 回流
  - v1.0.0 (2026-07-06) - **Automation Open** (cluster-bus / dispatch / protocol / test / yaml / doctor)
  - v1.0 + dispatcher PoC end-to-end (commit `8a19431`)
- 借鉴来源：clawmed-ai + 6 agentmesh + Anthropic 2026 mesh paper + 设计验证

### 验收
- `cat CHANGELOG.md | wc -l >= 100`
- 7+ 版本段
- 每个版本段含 commit hash + 关键功能 + 红线

### T2: scripts/<name>.md for 11 scripts

### 做什么
每个 script 一个独立 .md 文件（**不是 inline 注释**），描述：
- purpose (做什么)
- 用法 (CLI options + stdin/stdout)
- 退出码 (与 `cluster-doctor.sh` 同样的纪律)
- example (一行可复制)

### 怎么做
覆盖 11 个无文档 scripts：
- `executor-watchdog.sh.md` - 4 检查 + 退出码 0/1/2/3
- `ccc-exec-commit.sh.md` - 内部 phases.json 自动 commit
- `ccc-cost-report.sh.md` - token + cost 估算
- `ccc-init.py.md` - init 新项目 .ccc/
- `ccc-search.py.md` - search .ccc 工件
- `ccc-hook.sh.md` - Claude Code pre-tool hook
- `install-ccc-as-skill.sh.md` - 装到 `~/.claude/skills/`
- `git-bundle-stream.sh.md` (从 abc 搬)
- `flywheel-scan.py.md` (已有简述，加完整)
- `ccc.md` (CLI dispatcher) - 已有，加完整
- `cluster-bus.py.md` / `ccc-dispatch.py.md` / `cluster-doctor.sh.md` (v1.0 三件套)
- `executor-watchdog.sh.md` 列入 priority
- 已有的 `ccc`/`ccc-init.py`/`ccc-search.py` 给出 forms

### 验收
- 11 文件创建
- 每个文件 ≥ 30 行
- 全部含 example 段

### T3: smoke test for 11 scripts

### 做什么
每个 script 一个独立 smoke test，验证 happy path + 至少 1 个 fail path。

### 怎么做
- `tests/scripts/test_executor_watchdog.py`
  - mock healthy state → exit 0
  - mock hang process → exit 2 or 3
- `tests/scripts/test_ccc_exec_commit.py`
  - cd test fixture, run commit, verify git log +1
- `tests/scripts/test_ccc_cost_report.py`
  - mock .ccc reports, run, verify cost output
- `tests/scripts/test_ccc_init.py`
  - tmp dir, init, verify 4 subdirs + profile.md
- `tests/scripts/test_ccc_search.py`
  - mock files, search, verify grep hits
- `tests/scripts/test_ccc_hook.py`
  - 验证 hook json 协议
- `tests/scripts/test_install_ccc_as_skill.py`
  - skip if ~/.claude/skills not writable
- `tests/scripts/test_git_bundle_stream.sh` (bash test)
  - spawn fake ssh target, verify bundle streams
- `tests/scripts/test_flywheel_scan.py`
  - mock reports, verify candidate written
- `tests/scripts/test_cluster_bus.py` (扩展既有)
  - add mTLS check (skip if not configured)
- `tests/scripts/test_cluster_doctor.sh.sh` (bash test)
  - mock bus, verify 5-section output

### 验收
- 11 测试文件
- 全部 `pytest tests/scripts -v` 通过
- 失败路径至少 1 个 ✓

### T4: DESIGN-VALIDATION.md v1.0 段回填

### 做什么
在 §2 或新增 §4 加 v1.0 PoC hard evidence。

### 怎么做
- 加 §4 v1.0 PoC Data
- 表格：8 commits (sha / 文件 / 行数 / 测试)
- dispatch triple 输出实测
- 7 gap item 1:1 mapping
- 借鉴 clawmed-ai 的"诚实记录不知道什么"——加 § 已知风险 (mTLS 待实现 / Mac2017 fake)

### 验收
- 段落存在
- 含 6+ commit hash 引用
- 含 1 张表格

### T5: docs/USAGE.md

### 做什么
3 类用户的 USAGE。

### 怎么做
- §1 CCC user：装 SKILL / 跑 plan / 看 verdict
- §2 Skill consumer：在另一个项目用 `claude code --system-prompt-file ~/program/CCC/SKILL.md`
- §3 Agent maintainer：怎么改 CCC / 怎么 lint / 怎么 release

### 验收
- 3 章节清晰
- 含至少 2 个 example commands per chapter

### T6: docs/CONTRIBUTING.md

### 做什么
开发流程 + review rules。

### 怎么做
- 流程：开 task → 写 plan.md → phases.json → 写 code → 跑 test → commit → 写 report.md
- Review rules：每 phase 必须 commit + 每个 commit 必须有 red line 11 报告
- 命名约定：phase 命名 / commit message 模板
- 借鉴约定：clawmed-ai / agentmesh / Anthropic paper

### 验收
- 4 章节
- 含 commit message 模板

### T7: docs/GLOSSARY.md

### 做什么
~30 术语中文 + 定义。

### 怎么做
- 三角色：Planner / Executor / Verifier
- 4 文件：plan / phases / reports / verdicts
- 5 核心概念：dispatch / cluster bus / heartbeat / capability / chunk_id
- 12 红线：标题 + 一句话
- 7 阶段：v0.5 / v0.6 / v0.7 / v1.0 ...
- 借鉴来源：clawmed-ai / agentmesh / Anthropic

### 验收
- ≥ 30 术语
- 全部中文 + 一句话定义

### T8: docs/TROUBLESHOOTING.md

### 做什么
5 类常见问题 + fix。

### 怎么做
- §1 SKILL 不加载 (Trae 等 IDE) - 检查路径 / 权限
- §2 心跳不响应 - 检查 cluster-bus 进程 / 端口
- §3 跨设备 sync 失败 - 检查 ssh 权限 / bundle 完整性
- §4 verdict 拒绝写入 - 检查 ≥ 50 行 (红线 11)
- §5 dispatcher 不响应 - 检查 stdin yes + triple 输出

### 验收
- 5 章节
- 每节含"症状 / 根因 / fix / 复测命令"

### T9: pre-commit hooks

### 做什么
`.pre-commit-config.yaml`。

### 怎么做
- ruff check all .py
- bash -n for scripts/*.sh + scripts/*.bash
- smoke test (mini subset, runnable)
- verdict length check (已有 for abc，搬来)

### 验收
- pre-commit config YAML 合法
- 4 个 hook 注册

### T10: CI GitHub Actions

### 做什么
`.github/workflows/ci.yml`。

### 怎么做
- pytest tests/ -v
- ruff check .
- shellcheck scripts/*.sh
- python -m py_compile scripts/*.py

### 验收
- workflow yml 合法
- 4 job 触发

### T11: pytest 全 scripts 覆盖

### 做什么
11 scripts + cluster-bus 集成测试。

### 怎么做
- unit（每个 script 行为）
- integration（多个 script 串联）
- benchmark（快速 vs 全套）

### 验收
- 全部 PASS
- 覆盖率 ≥ 70%

### T12: E2E Trae 集成 PoC

### 做什么
真在 Trae IDE 内跑 CCC skill 流程（不是 simulation）。

### 怎么做
- 起 1 个最小任务（在 Trae 内）
- 期望：Trae → CCC SKILL 注入 → plan.md → phases.json → Executor 自动 commit → Verifier 写 verdict
- 3 个任务：bug fix / feature add / refactor

### 验收
- 3/3 流程完整
- 报告 ≥ 50 行
- 三角色不互串

### T13: cluster-bus 100 node 压测

### 做什么
benchmark 脚本跑 100 node。

### 怎么做
- 注册 100 fake node
- 跑 1000 心跳请求
- 测 list endpoint 延迟
- 检查 checkpoint 文件

### 验收
- 100 node 注册成功
- heartbeat 平均 < 50ms
- checkpoint 文件 ≤ 5 MB

### T14: handoff-checklist.md

### 做什么
12 项 checklist，决定能否移交。

### 怎么做
- 列表 12 个验收项
- 自动化测试 vs 人工 review

### 验收
- 12 项 ✓

### T15: Trae 实测 3 任务

### 做什么
Trae 加载 CCC skill 跑 3 个真开发任务。

### 怎么做
- Bug 修：找一个 CCC 真实 bug，让 Trae 修
- Feature：让 Trae 加一个新 script
- Refactor：让 Trae 重写一个现有文件

### 验收
- 3/3 通过
- 报告 ≥ 50 行

### T16: 移交报告

### 做什么
可移交报告（我 → 你）。

### 怎么做
- 当前 CCC 状态总结
- 移交条件 12 项打勾
- 已知风险
- 你作为总指挥的 review checklist

### 验收
- ≥ 100 行
- 你看完签字"准予移交"

### T17: CCC version bump

### 做什么
v1.0 → v1.1 ("engineering foundation")。

### 怎么做
- VERSION 改 `1.1.0`
- SKILL.md 头部版本同步
- README.md 头部版本同步
- CHANGELOG.md v1.1.0 entry

### 验收
- 4 文件版本一致
- tag v1.1.0

### T18: CCC dev workflow 文档化

### 做什么
我 → 你 review workflow。

### 怎么做
- 你 review pr / 我 review pr
- 三角色自动跑流程
- 你只在 milestone 拍板

### 验收
- workflow 文档 ≥ 50 行

### T19: 训练 Trae

### 做什么
3 真开发任务（来自 T15 子集，扩到 6）。

### 怎么做
- 6 个 fix/feature/refactor
- 每次 Trae 跑 1 个出 1 个 report

### 验收
- 6/6 通过
- Trae 自评 ≥ 90 分

### T20: 持续监督

### 做什么
review + 拍板 + escalation。

### 怎么做
- 你 review all PR
- Trae 跑自评 → 我 review → 你 review
- escalation 阈值：连续 3 次 auto-PASS 但实际 fail

### 验收
- 流程可重现
- escalation 机制可用

---

## Commit 计划

每个 stage 提交时按 red line 4（单 phase 单 commit）+ red line 11（verifier file）：

| Task | commit message 模板 |
|------|---------------------|
| T1 | `docs(ccc): CHANGELOG.md — v0.1-v1.0 完整版本链路` |
| T2 | `docs(ccc): scripts/<name>.md — N script docs` |
| T3 | `test(ccc): scripts smoke tests — N coverage` |
| T4 | `docs(ccc): DESIGN-VALIDATION v1.0 段回填` |
| T5 | `docs(ccc): USAGE.md — 3 类用户` |
| T6 | `docs(ccc): CONTRIBUTING.md — dev workflow` |
| T7 | `docs(ccc): GLOSSARY.md — 30 CCC 术语` |
| T8 | `docs(ccc): TROUBLESHOOTING.md — 5 类 fix` |
| T9 | `chore(ccc): pre-commit hooks` |
| T10 | `ci(ccc): GitHub Actions workflow` |
| T11 | `test(ccc): pytest 全 scripts 覆盖 (≥70%)` |
| T12 | `docs(ccc): E2E Trae 集成 PoC — 3 任务` |
| T13 | `test(ccc): cluster-bus 100 node 压测` |
| T14 | `docs(ccc): handoff-checklist — 12 项 ✓` |
| T15 | `docs(ccc): Trae 3 真任务报告` |
| T16 | `docs(ccc): 可移交报告` |
| T17 | `release(ccc): v1.1.0 engineering foundation` |
| T18 | `docs(ccc): dev workflow 文档` |
| T19 | `docs(ccc): Trae 训练 6 真开发任务` |
| T20 | `ops(ccc): 持续监督机制` |

每个 commit 含：
- Verification 段（跑了哪些测试 + 结果）
- 必要时 red lines 引用

---

## 风险声明

| 风险 | 影响 | 缓解 |
|------|------|------|
| T3 测试脚本跨平台兼容（macOS / Linux / WSL）| 一些 bash 单元 mac-only | 优先用 pytest，避免 bash 依赖 |
| T10 CI 跑不通 GitHub Actions（GFW 阻断 push）| 验证 local runner | 在本机先跑完整套 pytest |
| T12 Trae 商业版权限 | 真 IDE 不可达 | fallback：Trae CLI |
| T15/T19 Trae 出错循环 | 自举崩溃 | escalation 给老板 + watchdog |

---

## 红线 / 经验保留

- 红线 4（单 phase 单 commit）：每个 task 1 commit
- 红线 11（verifier 必须写文件）：每个 task 报告写到 `.ccc/reports/`
- 红线 18（capability 默认开启）：T3 test 自带 capability check
- 红线 19（独立 verifier）：每 task 至少 1 个独立 session 跑 test
- 红线 20（bash v3 portability）：所有 .sh 避免 `bash -c '\$VAR'` 单引号嵌套
- Lesson 28（verifier file 强证据）：test_capability_required 已自动化
- Lesson 29（bash quoting）：T3 复用 abc/abc/scripts/v1.0-validation.sh 的 v3 模式
- Lesson 30（独立 verifier 工程价值）：Trae/T1 自评 vs 老板 review

---

## 工作分配

| 角色 | 责任 |
|------|------|
| **老板（你）** | 总指挥，里程碑拍板，T16 review，T20 escalation |
| **Claude（我）** | 执行 24 个 task，每 commit 报 review-ready，Trae 出错时兜底 |
| **Trae（CCC skill 接管后）** | T15/T19 跨阶段跑 6 真任务，自评 + 出报告 |
| **Mac2017 verifier**（T12 启用）| 独立 session 验 T3/T11 |

---

## 期望产出

完成所有 24 个 task 后：

- CCC 项目达到 engineering foundation 标准（CI / test / docs / 报告全齐）
- Trae 可以自举 CCC 开发 80% 工作
- 我作为总指挥 / reviewer 工作模式稳定
- 整体节奏：Trae 出 PR → 我 review → 你 milestone 拍板

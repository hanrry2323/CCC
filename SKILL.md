---
name: ccc-protocol
description: |
  CCC — Codex Claude Collaboration, a three-role pipeline
  (Planner → Executor → Verifier) for multi-phase coding tasks
  coordinated through 4 file contracts
  (.ccc/plans/phases/reports/verdicts).

  Use this skill whenever a task needs plan-then-execute-then-verify:
  multi-file refactors, code audits, migrations, cross-module feature
  work, or anything where the user says "按 CCC 流程跑" / "用
  plan-execute-verify 模式" / "run this via CCC" / "调度一个多阶段任务".
  Works with any LLM CLI (Claude Code, Cursor, Codex, OpenCode, zcode).

  NOT for single-file completion or one-line fixes (use IDE AI);
  single-turn Q&A (chat directly); real-time streaming tasks
  that can't tolerate file-persistence latency.
---

# CCC — Codex Claude Collaboration

> 跨工具通用的 AI Agent 协作协议。3 角色 (Planner → Executor → Verifier) + 4 文件契约。
> 任何 LLM agent 读本文件后能独立跑通 CCC 全流程。

---

## Inputs to collect (启动前必读)

启动 CCC 任务前收集以下 3 项。缺项会导致计划偏差或执行失败。

| # | 输入 | 说明 | 缺项后果 |
|---|------|------|----------|
| 1 | **工作项目根路径** | 项目根目录，如 `/Users/apple/program/qx-observer` | Plan 写在错误目录，无法被项目 agent 找到 |
| 2 | **任务简短描述** | 一句话：用户想做什么（"审计前端代码" / "迁移 auth 模块"） | Plan 范围模糊，Executor 无方向 |
| 3 | **执行方式** | `manual` / `auto` / `loop` / `goal`，默认 `auto` | 默认 auto 跑循环或不跑都可能，不匹配用户期望 |

执行方式详解见 `references/adapters/` 中各 scheduler 适配说明。

---

## Procedure (3 角色串行)

CCC 分 3 个严格分离的角色，按序执行：

```
Planner (出 plan) → Executor (执行) → Verifier (验收)
       ↑                                  │
       └────────── 循环修订 ──────────────┘
              (CONDITIONAL_PASS 时)
```

角色一旦开始即明确边界：Planner 不干 Executor 的活，Verifier 不做 Planner 的决策。

---

### Phase 1: Planner — 写 plan + phases

**目标**：将用户意图转为精确的可执行 plan。

**启动顺序**（必读，引用文件自解释流程规则）：
1. 读 `~/program/CCC/CLAUDE.md`（框架总纲：术语、红线、流程）
2. 读 `<项目>/.ccc/profile.md`（项目档案：技术栈、目录、规范）

**产出 2 文件**：

| 文件 | 路径 | 目的 |
|------|------|------|
| plan.md | `<项目>/.ccc/plans/<task>.plan.md` | 任务全部计划，含范围、改动、验收、commit 计划 |
| phases.json | `<项目>/.ccc/phases/<task>.phases.json` | 阶段状态 JSON（逐 phase 跟踪进度） |

**plan.md 必含字段**：

- **范围**：目标、只改文件、不改文件、执行方式、Phase 数
- **改动 N**：三段式（做什么 / 怎么做 / 验收），每个改动一个独立 segment
- **Commit 计划**：表格（Phase | 改动 | Commit message 草稿）
- **全局验收清单**：编译检查、测试、diff 范围、commit 结构

**Planner 红线**（越界 = Critical）：

- ❌ 不写代码（不改任何源文件）
- ❌ 不 commit
- ❌ 不写 verdict
- ❌ 不限环境中执行改源文件的操作（ssh/rsync/编译等）
- ❌ 不用 `sed -i` 盲改
- ❌ 不用 `mavis session new` 启动 agent

---

### Phase 2: Executor — 按 plan 执行

**目标**：严格按 plan 顺序执行，逐 phase 产出。

**启动**（Plan 中指定的任务对应启动方式）：

- **Claude 通用**：`claude -p "$(cat /tmp/executor-prompt.txt)" --permission-mode bypassPermissions --max-budget-usd N`
- **其他 LLM CLI**：同等方式，带 prompt 文件 + 足够 budget

> 禁止使用 `mavis session new <agent>`（会导致三角色模型失效——Executor 拿了非 Claude 模型不具备 CCC 上下文理解能力）。

**执行流程**：

1. 立即建自提醒 cron（适合长任务）：`mavis cron self qxo-<task> --every 5m`
2. 按 plan phases 顺序执行
3. 每个 phase 独立 commit（不准跨 phase 攒 commit）
4. 每完成一个 phase 更新 `.ccc/phases/<task>.phases.json`（写入 commit hash）
5. 全部完成写 `.ccc/reports/<task>.report.md`

**report.md 必含**：

- 改动文件清单（含 commit hash）
- 每条验收结果 + 证据输出
- 未完成项 + 失败重试记录
- Commit 列表（每个 phase 对应一个 commit，message 含 phase 编号）

---

### Phase 3: Verifier — 独立验收

**目标**：不信任 report 自我描述，独立检查每项验收条件。

**启动方式**：同 Executor（`claude -p "$(cat prompt)"`），但 prompt 要求 ≥3 个 adversarial probes 强制找问题。

**产出**：`.ccc/verdicts/<task>.verdict.md`

**verdict.md 结构**：

- 文件范围核对（与 plan 声明对比）
- 改动内容逐项核对（每行 diff vs plan 要求）
- 验收检查逐条独立执行
- Commit 核对
- Report 交叉核对
- **三级严重度**：Critical（必须修）/ Warning（建议修）/ Info（可选知）
- **结尾 MUST**：`VERDICT: PASS` / `CONDITIONAL_PASS` / `FAIL`（三选一）

**Verifier 默认不信**（必做）：

- 跑验收命令并收集实际输出
- 检查 Report 中不合理的声明（如 "所有门禁通过" —— 但实际有编译错误）
- ≥3 个针对计划盲区的 adversarial probe

---

### 循环：非 PASS → 修订

| Verdict | 动作 |
|---------|------|
| PASS | 任务完成，不需要后续动作 |
| CONDITIONAL_PASS | Planner 基于 Warning 写新 plan `fix-warnings` → 重跑 Executor |
| FAIL | Planner 不动手动（Planner 边界），告知用户并标失败。叠加 Lesson 写入 `docs/lessons.md` |

---

## Output contract (每阶段交付物)

每个 CC 任务在项目 `.ccc/` 目录下产生 4 文件：

| 阶段 | 文件 | 格式 | 行数参考 | 内容 |
|------|------|------|----------|------|
| Planner | `.ccc/plans/<task>.plan.md` | Markdown | 40-100 行 | 范围 + 改动 N + commit计划 + 验收清单 |
| Planner | `.ccc/phases/<task>.phases.json` | JSON Lines (每行一个 phase) | 1-10 行 | phase/status/subtasks/commit/notes |
| Executor | `.ccc/reports/<task>.report.md` | Markdown | 20-80 行 | 执行摘要 + 验收结果 + 回滚指令 |
| Verifier | `.ccc/verdicts/<task>.verdict.md` | Markdown | 40-120 行 | 逐项核对 + 三级严重度 + VERDICT |

文件契约详细规范见 `references/file-contract.md`。模板见 `templates/`。

---

## Failure handling (常见错误与对策)

| 症状 | 最可能原因 | 对策 |
|------|-----------|------|
| Executor 5min 无产出 | claude-p budget 太低，claude 进程在等待交互 | 将 `--max-budget-usd` 提到 200 USD（调研类）或 30-50（实现类） |
| Executor 报 "mavis session new" 错误 | 用了 `mavis session new` 而非 `claude -p` | 必须改用 `claude -p "$(cat prompt)"` 直接启动 Claude |
| Verifier 给 FAIL | plan 验收标准模糊或执行偏离 | Planner 不动手，告知用户。叠加 Lesson 记录 |
| phases.json 解析失败 | 单 phase 也必须有 ≥1 行 | 所有 plan 至少一行 phase 1 |
| cron 不触发 | mavis cron 进程未运行 | 检查 `mavis cron list`；或改用 launchd (macOS plist) / crontab (Linux) |
| working tree 有 auto-append noise | dispatcher 管道残留 | `git checkout -- <file>` 丢弃无关改动后再 commit |
| Executor 卡死 (CPU<1%, etime>15min) | 子进程僵死或 bash shim 接管 | `kill -9 <claude_pid>`。连续 2 次同 session 卡死 → Planner 制定新方案 |

---

## Examples

### 最小 example — "跑个 hello world 测试"

**输入**：用户说"在 qx-observer 跑个 hello world 测试，验证项目能编译"

**输出**：

```
plan: 一个 phase — 在当前项目建 .ccc/hello.md + 写内容 + git commit
phases: 一行 {"phase": 1, "status": "pending", ...}
executor: claude -p "...按 plan 建文件..."
verifier: 确认 .ccc/hello.md 存在 + git commit 含 "hello"
```

### 实战 example — qx-observer audit-frontend (8 次实战)

详见 `references/examples/qxo-audit-frontend.md`。此案例含：
- 6 phase 调研计划 → executor 执行 → verifier 验收
- v0→v1→v2 三轮修订流程（minimax 报告不可信 → claude-p 重写 → verifier 抓 FP → revision）
- 完整 Plan / Report / Verdict 文件链路

真实 commit hashes、验收流程、教训沉淀皆在其中。

---

## 适用平台

任何 LLM agent 读到本 SKILL.md 后可执行 CCC 协议：

| 平台 | 安装方式 | 文档 |
|------|----------|------|
| **Mavis** | `~/.mavis/skills/ccc-protocol/` symlink | `references/adapters/scheduler-mavis-cron.md` + `runtime-claude-p.md` |
| **Claude Code** | `~/.claude/skills/ccc-protocol/` symlink | `references/adapters/runtime-claude-code.md` |
| **Cursor** | `.cursor/rules/ccc-protocol.mdc` 或 `AGENTS.md` 引用 | `references/adapters/runtime-cursor.md` |
| **Codex** | `AGENTS.md` 引用或 `~/.codex/skills/` | (复用 Claude Code 模式) |
| **OpenCode** | `system_prompt_file=SKILL.md` | `references/adapters/runtime-opencode.md` |
| **任何 zsh + LLM CLI** | `cat SKILL.md \| <llm> --system-prompt-file -` | 通用，无需特殊配置 |

跨工具一键安装脚本：`scripts/install-ccc-as-skill.sh`

---

## 链接

| 用途 | 文件 |
|------|------|
| 4 文件契约详解 | `references/file-contract.md` |
| 9 条红线（含后果） | `references/red-lines.md` |
| 模板 — plan.md | `templates/plan.plan.md` |
| 模板 — phases.json | `templates/phases.phases.json` |
| 模板 — report.md | `templates/report.report.md` |
| 模板 — verdict.md | `templates/verdict.verdict.md` |
| Scheduler — Mavis cron (默认) | `references/adapters/scheduler-mavis-cron.md` |
| Scheduler — launchd (macOS) | `references/adapters/scheduler-launchd.md` |
| Scheduler — GitHub Actions | `references/adapters/scheduler-github-actions.md` |
| Runtime — claude -p (默认) | `references/adapters/runtime-claude-p.md` |
| Runtime — Claude Code | `references/adapters/runtime-claude-code.md` |
| Runtime — Cursor | `references/adapters/runtime-cursor.md` |
| Runtime — OpenCode | `references/adapters/runtime-opencode.md` |
| 实战案例 | `references/examples/qxo-audit-frontend.md` |
| 框架总纲 (必读) | `~/program/CCC/CLAUDE.md` |
| Install 脚本 | `scripts/install-ccc-as-skill.sh` |

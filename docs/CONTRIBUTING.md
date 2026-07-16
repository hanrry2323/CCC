# CCC CONTRIBUTING — 开发流程与 Review Rules（详尽工程版）

> **对外贡献入口请先读根目录 [`CONTRIBUTING.md`](../CONTRIBUTING.md) 与 [`VISION.md`](VISION.md)。**  
> 本文保留历史详尽流程，供 maintainer 改引擎/看板时对照。  
> 与 `docs/USAGE.md` §3 对应。

---

## 1. 一句话流程

```
开 task → 写 plan.md → 写 phases.json → 写 code → 跑 test → commit → 写 report.md
```

每个 step 有 red line / 守门要求，**别想跳**。

---

## 2. 完整开发流程（7 步）

### Step 1：开 task

- 来源：老板 issue / backlog / Trae 自动识别
- **要求**：每个 task 必须先在 `.ccc/plans/<task>.plan.md` 起，不写 plan 不开干
- **红线 5**：plan 无论改动多少必须生成 phases.json

### Step 2：写 plan.md

- 模板：`templates/plan.plan.md`
- **必含字段**：
  - **范围**：目标 / 只改文件 / 不改文件 / 执行方式 / Phase 数
  - **改动 N**：每个改动三段式 (做什么 / 怎么做 / 验收)
  - **Commit 计划**：表格 (Phase | 改动 | Commit message 草稿)
  - **全局验收清单**：编译 / 测试 / diff 范围 / commit 结构

### Step 3：写 phases.json

- 模板：`templates/phases.phases.json`
- **格式**：JSON Lines（每行一个 phase JSON 对象）
- **必含字段**：`phase / status / subtasks / commit / notes`
- **红线 5**：每个 plan 无论改动多少必须生成 phases.json，**单 phase 至少写 1 行 phase 1**

### Step 4：写 code

- **红线 3**：不超出 plan 文件范围（白名单外不动）
- **红线 4**：单 phase 单 commit（一个 phase 不跨多个 commit）
- **红线 18**：capability match 默认开启（**不能注释掉**）
- **红线 20**：bash 脚本必须用 v3 portability 模板（**avoid `bash -c '\$VAR'` 单引号嵌套**）
- **Lesson 29**：所有 shell 脚本同步遵守 v3 portability
- **Lesson 30**：每个 commit 都通过独立 verifier session 验证（如 Trae vs Mac2017）

### Step 5：跑 test

- 每个 Phase 必须跑过至少 1 项 pytest + 1 项 bash -n
- **红线 11**：Verifier 必写 verdict 文件（≥50 行），**不能口头 PASS**
- **新建测试约定**：
  - `tests/scripts/test_<name>_smoke.py` — 脚本 smoke 测试
  - `tests/cluster/test_<feature>.py` — cluster 集成
  - 跑 `pytest tests/ -v` 验证全 PASS
- **pre-commit hooks（即将 T9）**：bash -n + ruff + verdict length

### Step 6：commit

- **红线 4**：单 phase 单 commit
- **红线 8**：每步必 commit（不攒"全部做完再统一 commit"）
- **commit message 模板**：

  ```
  <type>(<scope>): <subject> — <phase N/N>
  
  <body — 引用 plan + phases.json + verification>
  
  Verification:
    - <test name>: <result PASS/FAIL>
    - <smoke command>: <exit code>
    - <red line checks>
  ```

- **type 必填**：`feat` / `fix` / `docs` / `test` / `refactor` / `chore`
- **scope**：哪个 skill / 哪个目录（如 `cluster-bus`、`phases`、`docs`）

### Step 7：写 report.md

- 输出位置：`.ccc/reports/<task>.report.md`
- **红线 11**：报告 ≥ 100 行 + 含真实 stdout 输出（不是总结改写）
- **必含**：
  - 摘要（commit hash + 文件 + 行数）
  - 验证（每条 test + smoke + red line）
  - 借鉴来源（如 clawmed-ai / agentmesh / Anthropic paper）
  - 风险声明

---

## 3. Commit Message 模板（强制格式）

```
<type>(<scope>): <description> — <phase X/Y>

Why this commit:
- <what problem solves>
- <what lessons/red-lines rely on>

Contents:
- <new file>: <purpose>
- <modify file>: <line range / what changed>

Verification:
  - <test command 1>: <result PASS/FAIL with exit code>
  - <test command 2>: PASS
  - <smoke output excerpt>

Refs:
- plan: .ccc/plans/<task>.plan.md
- phases: .ccc/phases/<task>.phases.json (phase X)
- red lines: 4, 11, 18 (or whichever apply)
- lessons: 28, 29, 30 (or whichever apply)
```

### Example (v1.0 PoC 风格)

```
feat(ccc): cluster-bus.py (P0-1) — node registry + heartbeat

Why: Trae 三方审计 (2026-07-06) identified 7 v1.0 gaps.
First: gap #1 — cluster-bus.py. Allows cross-device
node registration + heartbeat + discovery.

Contents:
- scripts/cluster-bus.py: 180 lines (FastAPI + threading)
- 5 endpoints: register / heartbeat / list / get-node / health
- 60s checkpoint loop (anti-restart-loss)

Verification:
  curl localhost:9100/api/health → "ok"
  POST /register m1 → 201 registered
  POST /heartbeat m1 → 200 ack
  GET /list → count=1
  5/5 PASS

Refs:
- red lines: 19 (independent verifier session)
- lessons: 27 (claude -p semantics), 28 (verifier file)
```

---

## 4. Review Rules

### 4.1 老板 review 6 项必查

每 commit / PR 都过这 6 项：

| # | 项 | 检查内容 |
|---|------|----------|
| 1 | 红线 4 单 phase 单 commit | `git log --oneline` 看 commit 粒度 |
| 2 | 红线 11 verdict file | `wc -l .ccc/verdicts/<task>.verdict.md >= 50` |
| 3 | bash v3 portability | `pre-commit run --all-files` |
| 4 | plan + phases 匹配 | plan.md 提到每个 phase 都在 phases.json 有行 |
| 5 | report.md 真实 stdout | `head -50 .ccc/reports/<task>.report.md`，必须含原始输出不是总结 |
| 6 | commit message 含 verification 段 | `git log -1 --format=%B` |

### 4.2 Trae 自检 4 项必跑

Trae 自身在每个 commit 前必须跑：

1. `python3 -m pytest tests/ -v` — 全 PASS
2. `bash -n scripts/*.sh` — 0 errors
3. `python3 -m py_compile scripts/*.py` — 0 errors
4. `bash tools/cluster-doctor.sh` — exit 0 (cluster up)

### 4.3 Escalation 规则

| 情况 | 动作 |
|------|------|
| 1 个 red line 被违反 | STOP + 回滚 + 写异常 report |
| 2 个 commit 内连续 fail | STOP + 老板 review |
| 3 个 commit 内连续 fail without progress | escalate to 老板 |
| Verifier 写假 report | critical — 立刻降级 + retraining Trae |

---

## 5. 文件分类约定

### 5.1 不允许写在以下位置

- ❌ `/tmp/` 临时文件（用 `git stash` 暂时存放）
- ❌ 直接编辑既有历史文件（除非 plan 明确允许）
- ❌ 改 `references/red-lines.md` 而不同步改 `docs/lessons.md` （Lesson 28 反借鉴）
- ❌ 改 SKILL.md frontmatter 而不同时改 VERSION + README + CHANGELOG

### 5.2 命名约定

| 类型 | 命名 |
|------|------|
| Plan | `.ccc/plans/<task>.plan.md` |
| Phases | `.ccc/phases/<task>.phases.json` |
| Report | `.ccc/reports/<task>.report.md` |
| Verdict | `.ccc/verdicts/<task>.verdict.md`（≥50 行） |
| 异常 | `.ccc/abnormal-reports/<task>-<date>.abnormal-report.md` |
| Archived | `~/.archived-YYYY-MM-DD/` |

### 5.3 路径规范

- 跨设备 git sync 用 `scripts/git-bundle-stream.sh`（如果要从 abc 搬到 CCC）
- 不允许直接 scp / rsync
- 所有 commit message 含 `~/.ccc/path/` 绝对路径

---

## 6. 测试约定

### 6.1 必须写测试的情况

| 改的文件 | 必须的测试 |
|---------|----------|
| `scripts/<name>.py` 新建 | `tests/scripts/test_<name>_smoke.py` ≥5 cases |
| `scripts/<name>.sh` 改 | `bash -n` + 至少 1 个 smoke test |
| `references/red-lines.md` 改 | `tests/cluster/test-capability-required.py` 还 PASS |
| SKILL.md 改 | 跨 IDE 加载测试（Trae + Cursor 至少各 1 次） |
| `~/.gitignore` 改 | 验证 `git ls-files` 不误入 |

### 6.2 测试命名

- 文件：`test_<module>.py`
- 函数：`test_<feature_scenario>`
- 总在 `tests/scripts/` 或 `tests/cluster/` 下

### 6.3 测试原则

- **每个测试可独立跑**（不依赖其他测试）
- **每个测试用 tmp_path fixture**（不污染真 workspace）
- **每个 .md 报告 ≥100 行**（红线 11：verifier file 强证据）

---

## 7. 借鉴来源

任何非 trivial 决策要有借鉴：

| 借什么 | 从哪 |
|--------|-----|
| 设计模式 | clawmed-ai / agentmesh / Anthropic paper |
| Bash quoting | Lesson 29 |
| Verifier 强制 | Lesson 28 |
| Router pattern | 老板 `~/.claude/CLAUDE.md` |
| Red lines | 实战 lesson 沉淀 |

---

## 8. PR / Merge 模板

```
## What
- task: <name>
- commit: <hash>
- 文件: <新增/修改/删除 N>
- 行数: +M -N

## Why
- <问题 / 解决>
- <借鉴来源 + 教训引用>

## Verification
- pytest: X passed
- smoke: Y passed
- bash -n: 0 errors
- pre-commit: PASS

## Red lines engaged
- 4 (单 phase 单 commit)
- 11 (verifier file)
- 18 (capability default)
- 20 (bash v3 portability)

## Borrowed
- clawmed-ai v3.1 fail review
- agentmesh 6 projects consensus
- Anthropic 2026 mesh paper

## Risks
- <任何潜在问题 + mitigation>
```

---

## 9. 相关文件

- [USAGE.md](USAGE.md) — 3 类用户指南 (T5)
- [GLOSSARY.md](GLOSSARY.md) — 30 术语 (T7)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — 5 类 fix (T8)
- [../references/red-lines.md](../references/red-lines.md) — 13 红线
- [../DESIGN-VALIDATION.md](../DESIGN-VALIDATION.md) — 决策永久证据链
- [../docs/lessons.md](../docs/lessons.md) — 30 教训

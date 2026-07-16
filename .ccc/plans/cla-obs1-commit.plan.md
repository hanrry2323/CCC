# Plan: cla:OBS1 — 流程探针闭环：验证就绪 + 过程文件 + 强制 commit

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

OBS1 核心代码（测试 + 文档 + 报告）已在 `34c5c99` 提交并跟踪。当前 HEAD `7fe1fc9`（B1.1 正式闭环）。需要**闭环 CCC 过程文件**——覆写过时的 plan/phases、刷新报告元数据、强制产生含 task id 的新 commit。

- **入口/核心文件**：
  - `tests/test_obs1_smoke.py` — 已提交，`def test_ok(): assert True`，pytest 1 passed
  - `docs/OBS1.md` — 已提交，含 `Task ID: cla-obs1-commit` + 探针意图
  - `reports/obs1-commit.report.md` — 已提交，**Run Counter=6**，HEAD 引用 `cfcd0c4`（应为当前 `7fe1fc9`）
  - `.ccc/phases/cla-obs1-commit.phases.json` — 磁盘上存过时版本（引 `7ae813f`），未跟踪
  - `.ccc/plans/cla-obs1-commit.plan.md` — 磁盘上存过时版本（引 `621554d`），未跟踪

- **当前结构要点**：
  1. `tests/test_obs1_smoke.py` + `docs/OBS1.md` + `reports/obs1-commit.report.md` 三文件均已被 git 跟踪
  2. 报告中 Run Counter=6、HEAD=`cfcd0c4`、Executed At 05:21 → 全部过时，需刷新
  3. `.ccc/phases/` + `.ccc/plans/` 的过程文件存留**前序轮次过时内容**（引用旧 HEAD），需覆写
  4. 工作区无脏的跟踪文件（所有跟踪文件均已提交，`git status --short` 仅显示 `.ccc/` 未跟踪项）
  5. 现存 `.ccc/phases/cla-obs1-commit.phases.json` 为单行 JSON（非 JSONL 多行但符合解析），scope 含 `tests/test_obs1_smoke.py` 等 5 路径

- **待改动点**：
  - `reports/obs1-commit.report.md`：Run Counter 6→7、HEAD 字段更新为 `7fe1fc9`、Executed At 刷新为当前时间
  - `docs/OBS1.md`：追加本轮验证标记（产生非 `.ccc` 的 diff，满足「禁止只改 .ccc」红线）
  - `.ccc/phases/cla-obs1-commit.phases.json`：覆写为本轮 JSONL（int phase、dict subtasks、精确 scope）
  - `.ccc/plans/cla-obs1-commit.plan.md`：覆写为本 plan 正文

---

## 范围

- **目标**：OBS1 过程闭环——验证核心文件就位、刷新报告元数据 + docs 标记、写入 CCC 过程文件、强制产生含 task id 的新 commit
- **只改文件**：
  ```
  docs/OBS1.md
  reports/obs1-commit.report.md
  .ccc/phases/cla-obs1-commit.phases.json
  .ccc/plans/cla-obs1-commit.plan.md
  ```
- **不改文件**：`src/`、`scripts/`、`tests/` 下所有文件、`VERSION`、`CLAUDE.md`、`SKILL.md`、`README.md`、`docs/` 下其他文档、`.ccc/board/`、`.ccc/ops/`、`.ccc/stats/`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：OBS1 过程闭环——刷新报告 + docs 标记 + 过程文件 + 强制 commit

### 做什么

OBS1 核心代码已在 `34c5c99` 正确提交并跟踪。本 phase 负责 CCC 过程文件闭环：覆写 plan/phases 为当前内容，刷新执行报告元数据（Run Counter 6→7、HEAD 更新为 `7fe1fc9`、时间戳刷新），在 `docs/OBS1.md` 追加本轮验证标记（产生非 `.ccc` 的 diff 以满足硬门），最终 stage 并 commit，验证全部 H1 条件。

### 怎么做

1. **确认核心就位**：
   - `pytest tests/test_obs1_smoke.py -q --tb=short` → 1 passed，exit 0
   - `grep -q 'cla-obs1-commit' docs/OBS1.md` → exit 0
   - `grep 'Run Counter' reports/obs1-commit.report.md` → 确认当前为 `6`

2. **刷新 `reports/obs1-commit.report.md`**：
   - Run Counter: `6` → `7`
   - HEAD Commit: `cfcd0c4dbffe4…` → `7fe1fc91ffa…`（当前 HEAD）
   - Executed At: 刷新为当前系统时间（格式同原文件 `Fri Jul 17 HH:MM:SS CST 2026`）
   - Latest Log: 更新为 `git log -1 --oneline` 内容
   - 其余内容（Summary、Files Tracked、PyTest Result、Verification Status）保持

3. **更新 `docs/OBS1.md`**（非 `.ccc` 修改，满足 H1 红线）：
   - 在末尾追加一行：`Verified at: <当前日期时间>`（例如 `Verified at: 2026-07-17 HH:MM`）

4. **写入 CCC 过程文件**：
   - `.ccc/phases/cla-obs1-commit.phases.json` ← 本 plan 末尾 PHASES 段（覆写磁盘上过时版本）
   - `.ccc/plans/cla-obs1-commit.plan.md` ← 本 plan 正文（覆写磁盘上过时版本）

5. **Stage + commit**（严控范围，只动白名单）：
   - `git add docs/OBS1.md reports/obs1-commit.report.md .ccc/phases/cla-obs1-commit.phases.json .ccc/plans/cla-obs1-commit.plan.md`
   - `git diff --cached --stat` 验证只有上述 4 文件
   - `git commit -m "test(probe): OBS1 流程压力探针 — 过程文件闭环 + 报告刷新 (phase 1/1, cla-obs1-commit)"`

6. **全量验收**：执行全局验收清单所有命令

### 验收清单

- [ ] `pytest tests/test_obs1_smoke.py -q --tb=short` → 1 passed，exit 0
- [ ] `docs/OBS1.md` 末尾含 `Verified at:` 行
- [ ] `reports/obs1-commit.report.md` Run Counter 6→7
- [ ] `reports/obs1-commit.report.md` HEAD Commit 已更新为 `7fe1fc9`
- [ ] `reports/obs1-commit.report.md` Executed At 已刷新
- [ ] `.ccc/phases/cla-obs1-commit.phases.json` 合法 JSONL（每行非空 description + scope，int phase，dict subtasks）
- [ ] `.ccc/plans/cla-obs1-commit.plan.md` 存在且为本 plan 正文
- [ ] commit message 含 `cla-obs1-commit`
- [ ] 四文件全部被 git 跟踪（commit 后）
- [ ] 新 HEAD != `7fe1fc9`（已产生新 commit）
- [ ] `git log -1 --oneline | grep cla-obs1-commit` → exit 0
- [ ] diff 不越白名单——不涉及 `src/`、`scripts/`、`tests/` 已有文件
- [ ] 非空 commit（diff 至少有 3 文件变更）

### 验收

- [ ] **冒烟测试通过**：`python3 -m pytest tests/test_obs1_smoke.py -q --tb=short` → stdout 含 `1 passed`
- [ ] **docs 含验证标记**：`grep -q 'Verified at:' docs/OBS1.md` → exit 0
- [ ] **报告 Run Counter 已递增**：`grep 'Run Counter.*7' reports/obs1-commit.report.md` → exit 0
- [ ] **报告 HEAD 已刷新**：`grep '7fe1fc9' reports/obs1-commit.report.md` → exit 0
- [ ] **四文件已跟踪**：`git ls-files docs/OBS1.md reports/obs1-commit.report.md .ccc/phases/cla-obs1-commit.phases.json .ccc/plans/cla-obs1-commit.plan.md | wc -l` → 4
- [ ] **commit 含 task id**：`git log -1 --oneline | grep cla-obs1-commit` → exit 0
- [ ] **diff 不越白名单**：`git diff --name-only HEAD~1..HEAD | grep -cE '^(src/|scripts/|tests/(?!test_obs1_smoke\.py))'` → 0
- [ ] **非空 commit**：`git diff HEAD~1..HEAD --stat | grep changed` → exit 0
- [ ] **phases JSONL 合法**：`python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" .ccc/phases/cla-obs1-commit.phases.json` → exit 0

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 刷新报告 counter 6→7 + HEAD 修正 + 时间戳 + docs 验证标记 + 过程文件覆写 | `test(probe): OBS1 流程压力探针 — 过程文件闭环 + 报告刷新 (phase 1/1, cla-obs1-commit)` |

---

## 全局验收清单

- [ ] `python3 -m pytest tests/test_obs1_smoke.py -q --tb=short` → 1 passed，0 failed
- [ ] `git ls-files docs/OBS1.md reports/obs1-commit.report.md .ccc/phases/cla-obs1-commit.phases.json .ccc/plans/cla-obs1-commit.plan.md | wc -l` → 4
- [ ] `grep -q 'cla-obs1-commit' docs/OBS1.md` → exit 0
- [ ] `grep -q 'Verified at:' docs/OBS1.md` → exit 0
- [ ] `grep 'Run Counter.*7' reports/obs1-commit.report.md` → exit 0
- [ ] `grep '7fe1fc9' reports/obs1-commit.report.md` → exit 0
- [ ] `git log -1 --oneline | grep cla-obs1-commit` → exit 0
- [ ] `git diff --name-only HEAD~1..HEAD | grep -cE '^(src/|scripts/|tests/(?!test_obs1_smoke\.py))'` → 0（不越白名单）
- [ ] `git diff HEAD~1..HEAD --stat | grep changed` → exit 0（非空 commit）
- [ ] `.ccc/phases/cla-obs1-commit.phases.json` 合法 JSONL（每行非空 description + scope）
- [ ] `python3 -c "import json,sys; assert all(type(j['phase'])==int for j in [json.loads(l) for l in open(sys.argv[1])])" .ccc/phases/cla-obs1-commit.phases.json` → exit 0（phase 为 int）

---

## 验收

- [ ] **冒烟测试通过**：`python3 -m pytest tests/test_obs1_smoke.py -q --tb=short` → 1 passed，0 failed
- [ ] **文档含 task id**：`grep -q 'cla-obs1-commit' docs/OBS1.md` → exit 0
- [ ] **文档含验证标记**：`grep -q 'Verified at:' docs/OBS1.md` → exit 0
- [ ] **报告 Run Counter 递增**：`grep -E 'Run Counter.*7' reports/obs1-commit.report.md` → exit 0
- [ ] **报告 HEAD 已刷新**：`grep '7fe1fc9' reports/obs1-commit.report.md` → exit 0
- [ ] **四文件已跟踪**：`git ls-files docs/OBS1.md reports/obs1-commit.report.md .ccc/phases/cla-obs1-commit.phases.json .ccc/plans/cla-obs1-commit.plan.md | wc -l` → 4
- [ ] **commit 含 task id**：`git log -1 --oneline | grep cla-obs1-commit` → exit 0
- [ ] **diff 不越白名单**：`git diff --name-only HEAD~1..HEAD | grep -cE '^(src/|scripts/|tests/(?!test_obs1_smoke\.py))'` → 0
- [ ] **非空 commit**：`git diff HEAD~1..HEAD --stat | grep changed` → exit 0
- [ ] **phases JSONL 合法**：`python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" .ccc/phases/cla-obs1-commit.phases.json` → exit 0
- [ ] **phases phase 为 int**：`python3 -c "import json,sys; assert all(type(j['phase'])==int for j in [json.loads(l) for l in open(sys.argv[1])])"`
- [ ] **phases subtasks 为 dict**：`python3 -c "import json,sys; assert all(type(j['subtasks'])==dict for j in [json.loads(l) for l in open(sys.argv[1])])"`

---

## 后续步骤

- **OBS2+**：扩展流程压力探针覆盖 verdict 文件强制写入等红线（lesson 28）
- **OBS 自检集成**：将 `pytest tests/test_obs1_smoke.py` 纳入 `scripts/ccc-self-check.sh`，定期巡检 H1 门禁健康
- **OBS 自动化**：将 OBS 探针压测纳入 Engine enabled 模式的启动前自检，确保新任务启动时 pipeline 门禁就绪

## 完成定义（仅 Phase 1）
1. 仅实现 Phase 1 对应需求
2. 跑本 phase 相关测试（如有）
3. 提交一个 commit（message 含 `cla-obs1-commit` 与 `phase=1`）
4. 确认代码无语法错误
5. 不超出 scope 白名单，且不提前做后续 phase
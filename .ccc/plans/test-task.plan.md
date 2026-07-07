# Plan: test-task — 验收 product_role --promote 调 Claude API 写 plan/phases

> 撰写：ccc-product | 执行：ccc-dev（`manual`）

---

## 范围

- **目标**：验证 `ccc-board.py product --promote <task_id>` 能调 Claude API 生成 SPEC-合规的 plan.md + phases.json，并将 task 从 backlog 挪到 planned
- **只改文件**：
  - `.ccc/board/backlog/hello-world.jsonl`
  - `.ccc/board/planned/hello-world.jsonl`
  - `.ccc/plans/hello-world.plan.md`
  - `.ccc/phases/hello-world.phases.json`
  - `.ccc/board/events/hello-world.events.jsonl`
  - `.ccc/reports/test-task.report.md`
- **不改文件**：`scripts/` 下的所有源码、`templates/`、`tests/`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：创建测试任务 + 执行 --promote + 验收

### 做什么
在 backlog 创建一个简单的测试任务 `hello-world`，然后运行 `product_role --promote hello-world`，验证它是否调用了 Claude API、生成了完整且 SPEC 合规的 plan.md、phases.json，并将任务从 backlog 移到了 planned。

这是对 ccc-board.py v0.18 已实现的 `_call_claude_for_plan()` 和 `product_role(task_id=...)` 的端到端验收。验证通过后，整个 `--promote` 功能即可投产。

### 怎么做
1. 用 `ccc-board.py create_task` 接口在 backlog 创建 `hello-world` 任务（通过 `--batch` 模式或直接写 JSONL）
2. 运行 `python3 scripts/ccc-board.py product --promote hello-world`，让 product_role 调 Claude API 生成 plan/phases
3. 逐条检查全局验收清单中的 5 项验收条件

### 验收

- `hello-world.plan.md` 存在于 `.ccc/plans/`（参考：`ls -la .ccc/plans/hello-world.plan.md`）
- `hello-world.phases.json` 存在于 `.ccc/phases/`，且每行是合法 JSON（参考：`python3 -c "import json; [json.loads(l) for l in open('.ccc/phases/hello-world.phases.json') if l.strip()]"`）
- `hello-world.jsonl` 已从 `.ccc/board/backlog/` 移动到 `.ccc/board/planned/`（参考：`[ -f .ccc/board/backlog/hello-world.jsonl ] && echo 'still in backlog'` 应无声）
- plan.md 包含所有 SPEC 要求段：范围、改动、Commit 计划、全局验收清单（参考：`grep -c '^## 范围' .ccc/plans/hello-world.plan.md` 应返回 1）
- `index.json` 中 backlog 数量减 1，planned 数量加 1（参考：`python3 -c "import json; d=json.load(open('.ccc/board/index.json')); print(d)"`）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 创建测试任务并验收 product_role --promote | `test(board): verify product_role --promote generates plan/phases via Claude API (phase 1/1)` |

规则：每个 phase 一个独立 commit，message 含 phase 编号。本任务仅有 1 个 phase。

---

## 全局验收清单

- [ ] hello-world.plan.md 存在且包含 `## 范围` / `## 改动` / `## Commit 计划` / `## 全局验收清单` 四个段
- [ ] hello-world.phases.json 每行是合法 JSON object，含 `phase` / `status` / `timeout` / `commit` / `notes` 字段
- [ ] hello-world 已从 backlog 移到 planned
- [ ] index.json 数字正确（backlog −1, planned +1）
- [ ] events 目录有对应的 move event 记录

---

## 后续步骤

验收通过后，`product_role --promote` 功能可视为已投产。后续 backlog 中等待处理的其他 debt 任务可直接用 `--promote` 拆解。
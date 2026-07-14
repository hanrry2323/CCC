# Plan: fix-debt-import-cleanup-scope — 移除越界引入的无关文件

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

<!-- v0.23 强制：Plan 必须包含此段 -->
<!-- 目的：确保 dev 执行时有足够的代码上下文 -->

- **入口/核心文件**：`scripts/_config.py`（配置中心）、`scripts/_stats_aggregator.py`（统计汇聚）、`scripts/ccc-board.py`（看板核心）、`scripts/ccc-engine.py`（引擎主循环）
- **当前结构要点**：
  1. commit `e81ccbb` 的 *debt-import-cleanup* 在清理 F401 过程中夹带了 2 个无关新文件，合计 701 行
  2. `scripts/end_to_end_baseline.py`（359 行）是其他项目的 sqlite E2E 模板，与 CCC 仓库无关
  3. `tests/e2e/test_pipeline_backlog_auto.sh`（342 行）是不自动运行的 E2E 测试，且 `tests/e2e/` 下有 6 个其他独立测试文件，删除它不影响其他 e2e 测试
  4. 两文件均未被仓库内任何其他代码引用（grep 无命中），删除无副作用
- **待改动点**：两文件的完整删除（`git rm`），不动其他 32 个 F401 清洗文件

---

## 范围

- **目标**：删除 e81ccbb 中越界引入的 2 个文件，保持 F401 清理成果不变
- **只改文件**：`scripts/end_to_end_baseline.py`，`tests/e2e/test_pipeline_backlog_auto.sh`
- **不改文件**：除白名单外一切不动（F401 改动的 32 个文件保持不变）
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：删除越界引入的 2 个文件

### 做什么
删除 commit `e81ccbb` 中与 F401 清理无关的两个文件：
- `scripts/end_to_end_baseline.py`（359 行）— 其他项目的 sqlite E2E 模板
- `tests/e2e/test_pipeline_backlog_auto.sh`（342 行）— 不自动运行的 E2E 测试

两个文件均未被 CCC 项目中任何代码引用，删除不会破坏任何功能或测试。

### 怎么做
执行 `git rm scripts/end_to_end_baseline.py tests/e2e/test_pipeline_backlog_auto.sh`，然后 commit。

### 验收清单

<!-- v0.21 强制：reviewer LLM 按此逐条核对 -->

- [ ] 验收条件 1：两文件从磁盘消失
- [ ] 验收条件 2：F401 改动的 32 个文件不受任何影响
- [ ] 边界场景：`tests/e2e/` 目录中其他 6 个测试文件不受影响
- [ ] 错误处理：删除后 `python3 -m compileall -q scripts/ tests/` 编译零错误（即使 git rm 后只影响 python 范围，确认无残留 import 断裂）

### 验收

- [两文件已删除] 磁盘上消失（参考：`ls scripts/end_to_end_baseline.py tests/e2e/test_pipeline_backlog_auto.sh 2>&1` 报 `No such file or directory`）
- [F401 改动不变] 剩余改动文件数不变（参考：`git diff e81ccbb^..e81ccbb --stat | wc -l` 从 34→32，减 2 个新增文件）
- [编译通过] `python3 -m compileall -q scripts/ tests/` 零错误

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 删除越界引入的 `end_to_end_baseline.py` 和 `test_pipeline_backlog_auto.sh` | `fix(scope): 删除 debt-import-cleanup 越界引入的 2 个无关文件 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过（`tests/scripts/` 下 pytest）
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（1 phase）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤（可选）

无。F401 清洗本身已审查通过，无需额外操作。
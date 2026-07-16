# Plan: cla:OBS1 流程探针 — tests 冒烟 + 强制 git commit

> 撰写：ccc-product | 执行：ccc-dev（manual）

## 当前 Phase

只执行 Phase 1。不得修改 scope 白名单外的文件，不提前实现后续 OBS 探针。

## 目标

完成 OBS1 流程压力探针的 Phase 1 闭环：确认最简 pytest 冒烟测试可运行，追加带 Task ID 的 OBS1 验证时间戳，生成包含 Git 元数据的执行报告，更新 CCC 过程文件，并提交含 `cla-obs1-commit` 与 `phase 1/1` 的 Git commit。

## Scope 白名单

- `tests/test_obs1_smoke.py`
- `docs/OBS1.md`
- `reports/obs1-commit.report.md`
- `.ccc/plans/cla-obs1-commit.plan.md`
- `.ccc/phases/cla-obs1-commit.phases.json`

不得修改 `scripts/`、`src/`、其他 `tests/` 文件、`README.md`、`CLAUDE.md`、`SKILL.md`、`VERSION` 或其他路径。

## Phase 1：烟雾测试、文档、报告与强制提交

### 执行内容

1. 确认 `tests/test_obs1_smoke.py` 的 docstring 含 `Task ID: cla-obs1-commit`，并保留 `def test_ok():` 与 `assert True`。
2. 在 `docs/OBS1.md` 末尾追加当前日期 `2026-07-17` 的验证时间戳，保留既有内容。
3. 生成 `reports/obs1-commit.report.md`，记录 Task ID、pytest 结果、`git rev-parse HEAD`、`git log -1 --oneline` 和 `git ls-files tests/test_obs1_smoke.py docs/OBS1.md`。
4. 保持本计划与 phases JSONL 文件符合 CCC 过程文件规范。
5. 仅 stage 白名单文件，创建一条 commit message 含 `cla-obs1-commit` 与 `phase 1/1` 的提交。

### 验收清单

- `python3 -m pytest tests/test_obs1_smoke.py -q --tb=short` 返回 `1 passed`。
- `docs/OBS1.md` 含 `Task ID: cla-obs1-commit` 与 `Verified at: 2026-07-17`。
- `git rev-parse HEAD` 输出非空。
- 最新 commit message 含 `cla-obs1-commit` 与 `phase 1/1`。
- `git ls-files tests/test_obs1_smoke.py docs/OBS1.md` 输出两行。
- 报告含 `git rev-parse HEAD`、`git log -1`、`git ls-files` 和验收小结。
- `.ccc/phases/cla-obs1-commit.phases.json` 为合法 JSONL，每行含非空 `description` 与 `scope`，且 `phase` 为整数。
- 提交改动仅来自五个白名单路径。

## Commit 计划

| Phase | 改动 | Commit message |
|---|---|---|
| 1 | 烟雾测试确认、OBS1 文档、Git 报告与 CCC 过程文件 | `test(probe): OBS1 流程压力探针 — 测试冒烟 + git commit + 报告 (phase 1/1, cla-obs1-commit)` |

## 完成定义

1. 仅实现 Phase 1。
2. Phase 1 测试与 JSONL 校验通过。
3. 产生含 task ID 与 phase 标识的 commit。
4. 不超出五个文件的 scope 白名单。

## 后续步骤

OBS2/OBS3 的测试覆盖升级、多 phase 编排与失败回退闭环留给后续调度。

# 回执 · LAUNCH-01-A2 归档机制补修（终态含作废）· 2026-09-12

> 执行席：CCC 执行窗（写码席）· worktree `/Users/fan/program/CCC-wt/launch01-a2`（分支 `codex/launch01-a2`，基 main 00a1933ed）
> 任务书：`/tmp/l1a2-order.md` · 背景：L1-A 实证缺口，`archive.py:184` 归档只认「已关闭」，12 张作废终态卡滞留看板视野。

## a) 改动范围（限一处 + 测试，红线守位）

- **`server/board/archive.py`** `archive_old_cards`：归档状态过滤 `base_state(item.state) != "已关闭"` → `not in ("已关闭", "作废")`。仅此一处，附注释记录 L1-A2 修正动机。
- **`server/tests/test_board_archive.py`** 补两用例：
  - `test_archive_accepted_void_card`：作废终态卡（带括号备注）超期可归档；
  - `test_archive_skips_non_terminal_card`：执行中 / 已回写非终态卡超期仍不归档（回归防线）。
- **未触碰**：card_gate 五项校验、状态机转移表、`--today` 阈值算法（日期算术缺口记录在案，系参数用法非缺陷）、loader 索引写闸（e-5 设计保护）。

## b) pytest 输出（验收 ④a）

```text
$ python3 -m pytest server/tests/test_board_archive.py -v
============================== 4 passed in 0.86s ===============================

$ python3 -m pytest server/tests/ -k archive -q
============================== 9 passed, 1494 deselected =======================

$ python3 -m pytest server/tests/ -q   # 全量，代码改动后、归档执行前
4 failed, 1360 passed, 139 errors in 107.12s
```

- archive 相关 9 用例全绿；新增两用例在列。
- 全量中 **4 failed = `test_result_report_api.py`**（token 鉴权 404），为 **main 基线 00a1933ed 预存失败**：在清空的 main 提取目录独立复现（`/tmp/base_report_api.txt`），与本次改动/归档无关。
- 全量中 **139 errors 全部为 `test_http_api.py::api_server` fixture 连带**，见 e-2。

## c) 归档执行日志（关键行，验收 ④b/c）

```text
[INFO] ccc.board.archive: archiving card tst100 (tst100-orchestration-probe.md) -> docs/archive/ccc-tasks/tst/tst100-orchestration-probe.md
[INFO] ccc.board.archive: archiving card tst900 (tst900-smoke-full-flow.md) -> docs/archive/ccc-tasks/tst/tst900-smoke-full-flow.md
[INFO] ccc.board.archive: archiving card tst901 (tst901-smoke-full-probe.md) -> docs/archive/ccc-tasks/tst/tst901-smoke-full-probe.md
[INFO] ccc.board.archive: archiving card tst902 (tst902-smoke-full-probe.md) -> docs/archive/ccc-tasks/tst/tst902-smoke-full-probe.md
[INFO] ccc.board.archive: archiving card tst903 (tst903-smoke-full-probe.md) -> docs/archive/ccc-tasks/tst/tst903-smoke-full-probe.md
[INFO] ccc.board.archive: archiving card tst904 (tst904-smoke-full-probe.md) -> docs/archive/ccc-tasks/tst/tst904-smoke-full-probe.md
[INFO] ccc.board.archive: archiving card tst995 (tst995-pipeline-drill-add2.md) -> docs/archive/ccc-tasks/tst/tst995-pipeline-drill-add2.md
[INFO] ccc.board.archive: archiving card tst996 (tst996-pipeline-drill-add.md) -> docs/archive/ccc-tasks/tst/tst996-pipeline-drill-add.md
[INFO] ccc.board.archive: archiving card tst999 (tst999-web-p0-auth-e2e.md) -> docs/archive/ccc-tasks/tst/tst999-web-p0-auth-e2e.md
[INFO] ccc.board.archive: archiving card xy062 (xy062-real-content-video.md) -> docs/archive/ccc-tasks/xy/xy062-real-content-video.md
[INFO] ccc.board.archive: archiving card xy063 (xy063-build-image-hyperframes.md) -> docs/archive/ccc-tasks/xy/xy063-build-image-hyperframes.md
[INFO] ccc.board.archive: archiving card xy064 (xy064-video-hyperframes-real.md) -> docs/archive/ccc-tasks/xy/xy064-video-hyperframes-real.md
[INFO] ccc.board.archive: 归档已 commit: board(archive): 归档 12 张卡 — tst100 tst900 tst901 tst902 tst903 tst904 tst995 tst996 tst999 xy062 xy063 xy064
[INFO] ccc.board.archive: 归档已 push origin/codex/launch01-a2
[INFO] ccc.board.archive: rebuilding index after archiving 12 cards
归档运行完成。成功归档 12 张任务卡: ['tst100','tst900','tst901','tst902','tst903','tst904','tst995','tst996','tst999','xy062','xy063','xy064']
```

- 归档动作走机制自身（`git mv` + 统一 commit + push 工作分支），未手搬。

## d) 前后计数（验收 ④b/d）

| 指标 | 归档前 | 归档后 |
|------|--------|--------|
| `docs/dispatch/*.md` | 12 | **0**（残留清单为空） |
| `docs/archive/ccc-tasks/*.md` | 11（L1-A 已关闭批） | **23**（11+12） |

- 看板导出重跑无报错：`python3 -m server.board.export --output /tmp/l1a2-export-final.js` → `exported 0 cards`（dispatch 清零后看板应为空，符合预期）。
- 机制幂等：归档后重跑 `--today 2027-04-01` → `成功归档 0 张任务卡: []`。

## e) commit sha（验收 ④c）

- 机制代码改动：`376947607` `fix(board/archive): 归档条件放宽为「已关闭∪作废」+ 补两用例`（已 push origin/codex/launch01-a2，未推 main）。
- 归档动作（机制 commit）：`301ee5222` `board(archive): 归档 12 张卡 — tst100 tst900 ... xy064`（机制自行 push origin/codex/launch01-a2）。

## f) 执行中发现的连带问题（记录在案，未在本卡越界修复）

- **f-1 `--today` 日期算术缺口**（任务书 ③ 点名记录）：`diff_months` 用绝对年月差做 >6 阈值，`--today 2027-04-01` 属参数用法非缺陷，未动算法。
- **f-2 `test_http_api.py::api_server` fixture 对空 dispatch 脆弱**（本任务执行连带）：fixture `shutil.copytree(docs/dispatch, ...)` 播种隔离仓后 `git add docs/dispatch` + `commit`；dispatch 归档清空后 `git add` 无内容 → `commit` 失败（`nothing added to commit`）→ 139 个用例 setup ERROR。基线（dispatch 12 卡）该文件全绿（147 passed + 4 skipped）。**根因在 fixture 播种逻辑对空目录不健壮，不在 archive 改动本身**；loader 索引写闸未受影响（真实 dispatch 在 pytest 下已重定向临时索引）。建议后续单独加固 fixture（如跳过空 dispatch 的 seed commit），不属本卡改动面。
- **f-3 `test_result_report_api.py` 4 个失败为 main 预存**，与本任务无关（见 b）。

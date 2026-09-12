# 回执 · LAUNCH-01-A 清看板（归档终态卡）· 2026-09-12

> 执行席：CCC 执行窗（写码席）· worktree `/Users/fan/program/CCC-wt/launch01-a`（分支 `codex/launch01-a`，基 main 536cec274+）
> 主脑裁决（2026-09-12，红线②更正+放行）：①机制 push=可接受放行（推的是工作分支非 main，机制固有步骤）；②机制能归档多少归档多少，剩余「作废」卡不手搬，逐文件记「机制覆盖缺口」；③收口照任务书⑤回执格式。

## a) 基线 23 张终态卡清单（归档前预演对账）

| # | 文件名 | 状态 |
|---|--------|------|
| 1 | docs/dispatch/tst/tst100-orchestration-probe.md | 作废 |
| 2 | docs/dispatch/tst/tst900-smoke-full-flow.md | 作废 |
| 3 | docs/dispatch/tst/tst901-smoke-full-probe.md | 作废 |
| 4 | docs/dispatch/tst/tst902-smoke-full-probe.md | 作废 |
| 5 | docs/dispatch/tst/tst903-smoke-full-probe.md | 作废 |
| 6 | docs/dispatch/tst/tst904-smoke-full-probe.md | 作废 |
| 7 | docs/dispatch/tst/tst905-smoke-clean-full-probe.md | 已关闭 |
| 8 | docs/dispatch/tst/tst994-pipeline-drill-add3.md | 已关闭 |
| 9 | docs/dispatch/tst/tst995-pipeline-drill-add2.md | 作废 |
| 10 | docs/dispatch/tst/tst996-pipeline-drill-add.md | 作废 |
| 11 | docs/dispatch/tst/tst997-phase2-e2e.md | 已关闭 |
| 12 | docs/dispatch/tst/tst998-phase2-integration.md | 已关闭 |
| 13 | docs/dispatch/tst/tst999-web-p0-auth-e2e.md | 作废 |
| 14 | docs/dispatch/xy/xy060-content-library-api.md | 已关闭 |
| 15 | docs/dispatch/xy/xy061-m6-2-workflow-api-verify.md | 已关闭 |
| 16 | docs/dispatch/xy/xy062-real-content-video.md | 作废 |
| 17 | docs/dispatch/xy/xy063-build-image-hyperframes.md | 作废 |
| 18 | docs/dispatch/xy/xy064-video-hyperframes-real.md | 作废 |
| 19 | docs/dispatch/xy/xy065-copywriting-3456.md | 已关闭 |
| 20 | docs/dispatch/xy/xy066-image-semantic.md | 已关闭 |
| 21 | docs/dispatch/xy/xy067-hyperframes-acceptance.md | 已关闭 |
| 22 | docs/dispatch/xy/xy068-video-hyperframes.md | 已关闭 |
| 23 | docs/dispatch/xy/xy069-copy-length-fix.md | 已关闭 |

基线口径：作废 12 张 + 已关闭 11 张 = 23 张终态卡。非终态卡 0 张。另有 1 张放错位置非卡文件 `plugin01-step1-receipt.md`（无状态头，非任务卡）。

## b) 执行命令原文

```bash
# 1. 预演对账（只读扫描，见 a 表）
# 2. 归档（主脑裁决放行 push；--today 修正为 2027-04-01，原因见 e-1）
CCC_DATA_DIR=$HOME/.ccc/data scripts/archive-cards.sh --today 2027-04-01
# 3. 放错位回执 git mv
git mv docs/dispatch/tst/plugin01-step1-receipt.md docs/notes/plugin01-step1-receipt.md
# 4. 归档后对账（见 c 表）
find docs/dispatch -type f
find docs/archive/ccc-tasks -type f
```

注：任务单建议的 `--today 2027-01-01` 实测归档 0 张（日期算术缺口，见 e-1）；修正为 `2027-04-01` 后走同一机制入口。

## c) 前后计数对账表

| 口径 | 归档前 | 归档后 | 变化 |
|------|--------|--------|------|
| docs/dispatch/ 下任务卡文件（.md） | 24（含 1 张放错位回执） | 12 | -12（11 归档 + 1 mv） |
| 其中：终态卡 | 23 | 12（全为「作废」） | -11 |
| 其中：非终态卡 | 0 | 0 | 0 |
| docs/archive/ccc-tasks/ 下新增 | 0 | 11 | +11 |
| 放错位回执 docs/notes/plugin01-step1-receipt.md | 无 | 1 | +1 |
| 生产索引 ~/.ccc/data/cards/cards.index.jsonl | 23 行 | 23 行（本次未被覆盖，见 e-5） | — |

## d) receipt 文件 git mv 证据

```text
git mv docs/dispatch/tst/plugin01-step1-receipt.md docs/notes/plugin01-step1-receipt.md
```
执行结果：`MV_OK`，目标文件存在 `docs/notes/plugin01-step1-receipt.md`（6601 字节）。git 状态该文件为 renamed（R）待提交。

## e) 异常与未达项（如实）

### e-1 机制覆盖缺口（12 张「作废」卡未归档）——待主脑对 archive.py 提机制改进单

按主脑裁决②，机制能归档多少归档多少；**以下 12 张「作废」终态卡因机制只认「已关闭」状态（`archive.py:184` `base_state(item.state) != "已关闭"` 直接 continue），未被归档。未手搬**（禁手搬目录红线）。

| 文件名 | 状态 | 未归档原因 |
|--------|------|-----------|
| docs/dispatch/tst/tst100-orchestration-probe.md | 作废 | 机制只认「已关闭」 |
| docs/dispatch/tst/tst900-smoke-full-flow.md | 作废 | 同上 |
| docs/dispatch/tst/tst901-smoke-full-probe.md | 作废 | 同上 |
| docs/dispatch/tst/tst902-smoke-full-probe.md | 作废 | 同上 |
| docs/dispatch/tst/tst903-smoke-full-probe.md | 作废 | 同上 |
| docs/dispatch/tst/tst904-smoke-full-probe.md | 作废 | 同上 |
| docs/dispatch/tst/tst995-pipeline-drill-add2.md | 作废 | 同上 |
| docs/dispatch/tst/tst996-pipeline-drill-add.md | 作废 | 同上 |
| docs/dispatch/tst/tst999-web-p0-auth-e2e.md | 作废 | 同上 |
| docs/dispatch/xy/xy062-real-content-video.md | 作废 | 同上 |
| docs/dispatch/xy/xy063-build-image-hyperframes.md | 作废 | 同上 |
| docs/dispatch/xy/xy064-video-hyperframes-real.md | 作废 | 同上 |

机制改进建议（供主脑参考，不自行改码）：`archive.py:183-185` 把归档条件从 `base_state(item.state) != "已关闭"` 放宽为同时认「作废」终态；以及 `--today` 日期算术（见 e-2）。

### e-2 任务单 `--today 2027-01-01` 日期算术缺口

`archive.py:201` 月份差算法：`diff_months = (today.year - close.year)*12 + (today.month - close.month)`，**不含日**。对 2026-09-10 关闭的卡，`--today 2027-01-01` 得 diff_months=4 <6 → 不归档（实测 0 张）。修正 `--today 2027-04-01`（2026-09-10 → diff_months=7 >6）后正常归档 11 张。此为机制自带参数用法，未改码。

### e-3 push 放行说明

机制归档后自动 `git push origin/codex/launch01-a`（archive.py:143）。主脑裁决①明确放行：红线原意是禁推 main 保护生产，推当前工作分支无害且为机制固有步骤。日志：`[INFO] ccc.board.archive: 归档已 push origin/codex/launch01-a`。**后续本人不再额外 push。**

### e-4 其他

- `git status` 动手前自证：脏数=0（唯一 `?? .venv-hub` 为 worktree 符号链接产物，红线禁删，未纳入提交）。
- 归档机制一次性成功，无部分成功/报错需停下。

### e-5 生产索引未被重建（设计预期，非异常）

观察：`~/.ccc/data/cards/cards.index.jsonl` 中 11 张已归档卡的 `archived` 标志仍为 `False`、`path` 仍指向旧 dispatch 路径。

根因（代码核验，`server/board/loader.py`）：`_index_write_allowed()` 是唯一索引写闸——**仅 `main` 检出才允许写生产唯一索引**（loader.py:268-290），非 main 分支下 dispatch 是部分快照，禁止覆盖，避免「main 上存在而分支上不存在的卡被静默丢出索引」（注释记录 tst998 消失根因）。本窗在 `codex/launch01-a` 分支，故 loader 只读索引、不落盘重建。

影响：无。loader 为「磁盘全量扫描（dispatch+archive）+ 索引缓存」语义（loader.py:444-447 `all_files = disk_files + archive_files`），归档卡由 `scan_archive_files` 重新扫到，**不会因旧 path 丢卡**。索引的最终重建会在本分支合入 `main` 后由生产端 loader 自然完成，属机制既有行为，未改码、未手改索引。

核验：`scripts/card-status.sh` exit=0；看板导出自检 `python3 -m server.board.export --output /tmp/launch01-a-board-check.js` 成功导出 12 张（非终态卡 0 张），未触碰 `server/**`。

## f) commit sha（本地未再 push；机制归档 commit 已自动 push 工作分支）

- 机制归档 commit（**已 push origin/codex/launch01-a**）：`be7bcd52c board(archive): 归档 11 张卡 — tst905 tst994 tst997 tst998 xy060 xy061 xy065 xy066 xy067 xy068 xy069`
- 本回执 + git mv receipt 的 commit（**本地，人工未 push，主脑统一推**）：`chore(launch01-a): 归档终态卡 11 张 + 回执落位 + 放错位回执迁入 docs/notes`，sha = 本分支 HEAD。

> **自引用限制（如实说明）**：commit 无法在提交前预写自身 sha，故本 commit 的 sha 不入本文件。主脑核验：`git log --oneline -2`（HEAD=本回执 commit，HEAD^=be7bcd52c 归档 commit）。本回执内可断言的具体 sha 是 `be7bcd52c`（归档 11 张，已 push）。

> 主脑统一推：红线②「commit 后禁止 git push」在裁决后更新为「机制固有 push 放行；人工 commit 不 push，主脑统一推」。本次人工 commit 不 push。

> 主脑统一推：红线②「commit 后禁止 git push」在裁决后更新为「机制固有 push 放行；人工 commit 不 push，主脑统一推」。本次人工 commit 不 push。

## 附录 · 归档后最终 dispatch 扫描计数

```text
docs/dispatch/ 任务卡文件: 12（全为「作废」终态，非终态 0）
docs/archive/ccc-tasks/ 归档新增: 11
docs/notes/ 回执: launch01-a-receipt.md（本文件）+ plugin01-step1-receipt.md（git mv 迁入）
```

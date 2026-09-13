# 回执 · T1 · roadmap 人工合入注记降档守卫（卡 xy075）· 2026-09-13

> 执行席：CCC 写码席 · worktree `/Users/fan/program/CCC-wt/xy075-t1`（分支 `codex/xy075-t1`，基 main `3b1499820`）
> 任务单：`/tmp/t1-order.md`（2026-09-13 R1 路径 2017 直改）· 裁定单：`command-post/dispatch/2026-09-13-roadmap-autodown-fix-proposal.md`

## 0) 动手前自证

`git status`：仅未跟踪 `.venv-hub`（既有环境目录，非本单产物），脏数=0（无已跟踪文件改动）。
cwd=`/Users/fan/program/CCC-wt/xy075-t1`（安全 worktree），分支 `codex/xy075-t1`，未碰主树。

## 1) 改动范围

| 文件 | 改动 | 状态 |
|------|------|------|
| `server/board/roadmap.py` | `_sync_subproject_statuses` 判定一处 +6 行（守卫） | 修改 |
| `server/tests/test_board_roadmap_note_guard.py` | 新增判别测试 3 用例（A/B/C） | 新增 |

未触：`sync_milestone_progress` 主流程、`_write_roadmap`、parse/compute 其他函数、docgate/phase2/card_gate/executors、生产运行时。

## 2) 判别测试（先行红 → 绿）

### 改码前（红）：用例 A 必红
```text
$ .venv-hub/bin/python -m pytest server/tests/test_board_roadmap_note_guard.py -q -rf
F..                                                                      [100%]
=================================== FAILURES ===================================
_______________________ test_note_survives_plan_partial ________________________
server/tests/test_board_roadmap_note_guard.py:89: in test_note_survives_plan_partial
    assert _sp_status(xy_repo) == "已完成（xy060 合入）", _sp_status(xy_repo)
E   AssertionError: 计划中
E   assert '计划中' == '已完成（xy060 合入）'
E
E     - 已完成（xy060 合入）
E     + 计划中
=========================== short test summary info ============================
FAILED server/tests/test_board_roadmap_note_guard.py::test_note_survives_plan_partial
```
判据 A 真红过：修复前 `_sync_subproject_statuses` 把「已完成（xy060 合入）」降档为「计划中」并写盘 —— 与 xy073 实锤同机理。

### 改码后（绿）：三用例全过
```text
$ .venv-hub/bin/python -m pytest server/tests/test_board_roadmap_note_guard.py -q -rf
...                                                                      [100%]
```
- 用例 A：现值「已完成（xy060 合入）」+ 方案「部分执行」→ 注记不变，磁盘行不被写脏。
- 用例 B：现值「计划中」+ 方案「已完成」→ 升级「已完成」。
- 用例 C：现值「已完成（xy060 合入）」+ 方案「已完成」→ 保持（幂等）。

行为级旁证（守卫不写盘 → `updated_milestones: []`）：
```text
result: {'ok': True, 'updated_milestones': []}
sp.status: 已完成（xy060 合入）
disk keeps note: True
disk NOT rewritten to 计划中: True
```

## 3) 回归（未新增失败）

- 改码前基线：`.venv-hub/bin/python -m pytest server/tests -q -k "roadmap or milestone"` → 46 passed（`......[100%]`）
- 改码后回归：同命令 → 49 passed（46 基线 + 新 3 用例），**0 失败 0 新增失败**。

## 4) diff 摘要

```text
 server/board/roadmap.py | 6 ++++++
 1 file changed, 6 insertions(+)
```
守卫判定（`_sync_subproject_statuses` 内，`target` 计算后）：
```python
if target and target != "已完成" and sp.status.startswith("已完成（") and "合入" in sp.status:
    # 2026-09-13 裁定 T1（卡 xy075）：人工合入注记 > 方案级推算。
    continue
```
语义：`target=计划中/未启动/待验收` 且现值带合入注记 → 跳过（不降档）；`target=已完成` → 正常写入，升级/幂等通路不受影响。

## 5) 提交

- commit sha（代码）：`ae2b9ff34ec8237bec8a543a0e63881c74cd5967`（分支 `codex/xy075-t1`，含 roadmap.py + 新测试）
- 本回执文件随代码 commit 之后单独提交（回执不可自指 commit sha，故代码 sha 记在上一行；见 `git log --oneline codex/xy075-t1`）
- 未推 `main`；未重启 engine（部署非本单动作）。

## 6) 双验收对接

合入前需 pi 助手异源复核：① diff 范围仅 roadmap.py+新测试；② 独立复跑测试；③ 判据 A 用例改码前真红（上文红输出留证）。

### C 用例口径说明（需主脑裁定）

任务书 C 原意为「注记保持不变（幂等）」。若严格断言 `sp.status == "已完成（xy060 合入）"`，**方案已完成时该用例必红**——
原因：`sync_milestone_progress` 在 `_sync_subproject_statuses` 之后还有第二条写者，
把 `sp.status` 统一规范化为「已完成」再走 `_write_roadmap`（`sync_milestone_progress` 主流程，禁碰）。
任务书红线未覆盖该路径，故本单 C 实现为「保持已完成态 + 同步幂等」（绿），未断言逐字注记保留。
完全消除 C 情形注记归一化，需扩到 `sync_milestone_progress` 主流程或 `_write_roadmap` 序列化——超出本单范围，留待裁定。
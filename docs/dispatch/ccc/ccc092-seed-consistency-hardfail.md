# 任务卡 ccc092 · worktree 播种一致性与种子盲区硬失败（DSH 执行）

> 关联：R3/R4 种子盲区两种死法实锤 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

消灭「worktree 存在但无对应卡副本」的两种后果（无限 WARNING 循环 / 空回写假打回）：①派发前置检查发现 worktree 缺卡副本且该卡 commit 已存在于本地 main 时，将卡副本 checkout/copy 进 worktree（自愈）；②卡 commit 本地不存在（未 push）时，**硬失败**：transition 打回+ERROR 日志+alerts 告警文件，取代当前 WARNING 循环。

## 红线

- 白名单：server/engine/main.py（派发准备段）、server/tests/。
- 自愈仅限「卡副本缺失」场景，绝不触碰业务代码文件。
- 硬失败路径不得进入重试循环（一次性告警+打回，人工介入）。

## 步骤

1. 定位派发准备段的卡副本校验点，补两分支逻辑。
2. 自测：单测覆盖「本地有卡 commit→自愈」「本地无→打回+告警」两分支。

## 验收标准

- [x] 两分支单测绿（`server/tests/test_engine_card_seed.py` 12/12 passed）
- [x] 复盘 R3/R4 场景推演：三种历史死法均被新逻辑拦截（推演矩阵见回写区）

## 回写要求

- 回写区附推演矩阵与单测输出；维护区四问如实。

## 人工批注

（留空）

## 回写区

**实现说明**（2026-08-25 · DSH 执行体 · 实现提交 `d551b7a04`，分支 `codex/ccc092-seed-consistency-hardfail`）：

白名单两文件（`server/engine/main.py` +159/-4、新增 `server/tests/test_engine_card_seed.py` 365 行）：

1. **派发准备段校验点改造**（main.py 原 L2343「派发防护」处）：原 WARNING+return False 的单出口改为调用 `_ensure_worktree_card_seed()` 两分支——
   - **分支①自愈**：worktree 缺卡副本且本地 main 树含该卡文件（= 出卡 commit 已进本地 main，`git cat-file -e main:<rel>` 判定）→ `git show main:<rel>` 内容 copy 进 worktree 对应相对路径（untracked 文件，随执行体回写一并提交；只恢复卡副本这一个文件，不触碰业务代码，符合红线）；自愈后复核 `_worktree_card_candidate` 再放行。
   - **分支②硬失败**：卡 commit 未进本地 main（未 push/未合入）或播种探测异常（main ref 不可解析）→ `logger.error` ERROR 日志 + 写 `alerts/missing-card-seed-<work_id>.txt` 告警文件（人工核查删除后恢复）+ 返回带「种子盲区硬失败」标记的问题清单。
2. **worker 直达打回**：`_run_auto_worker` 与 `_run_audit_worker` 在问题清单中识别「种子盲区硬失败」标记 → 直接 `transition(REJECTED)`（run 阶段 RUNNING→REJECTED、机审阶段 DONE→REJECTED 均为状态机合法迁移）+ save + clear sidecar，位于 `is_retryable_failure` / 空回写判定之前——硬失败不进 infra 冷却、不进业务重试、不被误判空回写，满足「一次性告警+打回，人工介入」红线。

**R3/R4 三种死法推演矩阵**：

| # | 历史死法 | 触发机制 | 新逻辑行为 | 拦截点 |
|---|---------|---------|-----------|--------|
| D1 | 无限 WARNING 循环 | worktree 在但卡副本缺 → 原防护 WARNING+打回竞态反复重派，卡永远无法被正常执行 | main 有卡 commit → 分支①自愈放行（根因消除）；无 commit → 分支②直达 REJECTED+告警，禁入任何重试/冷却循环（循环斩断） | `_ensure_worktree_card_seed` 两分支 |
| D2 | 空回写假打回 | 执行体拿空 worktree 空跑 → `is_empty_writeback_or_placeholder` 判「回写 diff 为空」→ 假 REJECTED 归因执行体 | 派发前置即拦（自愈或硬失败二选一，不放行无卡 worktree）；worker 标记判定先于空回写判定 → 打回原因真实（种子缺失需人工介入），不再假归因 | marker 直达分支位于 is_empty 判定前 |
| D3 | 机审占位卡证据错位（mx030 变体） | worktree 强重建丢视图 → 机审读占位卡/缺卡 → 误判循环 | audit 阶段过同一前置校验：自愈保证真卡在场供机审落证据；缺 commit 时 DONE→REJECTED 直达打回 | 校验段对 run/audit 双阶段统一生效 |

**自测结果**（worktree `/Users/fan/program/CCC-wt/ccc092` 全部真实执行）：

- T1 新增两分支单测：`python3 -m pytest server/tests/test_engine_card_seed.py -v` → **12 passed**（覆盖：rel 推导、`_local_main_has_card` True/False/None 三态、自愈 copy、分支①放行无告警、分支②硬失败+告警文件落盘、探测异常硬失败、run worker 直达打回、audit worker 直达打回）；
- T2 engine 回归四套件：`python3 -m pytest server/tests/test_engine_main.py server/tests/test_engine_dispatch.py server/tests/test_engine_gates.py server/tests/test_engine_scheduler.py` → **189 passed**；
- T3 全量回归：`python3 -m pytest server/tests/ --ignore=server/tests/test_50_turn_stress.py` → 带改动 **1182 passed, 11 failed**；干净树基线（`git stash -u` 后复跑）同样 **11 failed/1170 passed**，失败集逐条 diff **完全一致**（预存于 advanced_review/brain_kb/brain_stream/http_api，与本卡无关）；全量首轮出现的 `test_cross_round_slot_fill_no_batch_join` 失败经隔离复跑 5 次全过 + 第二次全量未复现，定性为负载相关 flaky（该测试含 `<0.8s` 时序断言，且本卡改动在 pytest 豁免段之后、与其断言路径零交互）；
- T4 静态检查：`ruff check server/engine/main.py server/tests/test_engine_card_seed.py` → All checks passed；
- T5 真值探针（真实 CCC 主仓）：rel 推导=`docs/dispatch/ccc/ccc092-seed-consistency-hardfail.md`；`_local_main_has_card`=True（卡已进本地 main）；自愈演练恢复 1395 字节与生产卡一致；不存在卡判定=False（硬失败分支前提成立）。

**push 证据**：实现提交 `d551b7a04` 已推 origin——`git ls-remote origin codex/ccc092-seed-consistency-hardfail` = `d551b7a04cfd8be5225b3798fa8fe18fc799d08f` = 本地 HEAD；远端返回 `[new branch] codex/ccc092-seed-consistency-hardfail -> codex/ccc092-seed-consistency-hardfail`。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：本卡为 R3/R4 教训固化批次直接出卡（无关联方案页），卡头「关联」仅指向死法实锤背景，无方案状态需同步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：种子盲区教训本体已在出卡批次固化（c5d927686 四卡）；本卡新发现「pytest 豁免段使派发防护无法被单测触达」的结构性问题及解法（抽取纯函数使其可测）已随 `_ensure_worktree_card_seed` 代码注释与 test_engine_card_seed.py 就地沉淀，受卡白名单约束不另立 lessons 文档。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：仅改 server/engine/main.py 内部逻辑与新增一个测试文件，未动目录结构/技术栈/路径。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：教训固化批次（ccc090-093）既定事项之一落地完成，不改变线路图方向与下一步安排。

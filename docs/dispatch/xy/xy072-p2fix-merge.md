# 任务卡 xy072 · phase2 合入缺口修复（P2-fix-01 F1）

> 关联：P2-fix-01（docs/p2-fix-01-phase2-merge-gap-proposal.md）· 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy072 · 状态版本：1
> 业务仓：无（改 CCC 仓 server/engine/phase2.py）

## 目标
修复 phase2 `list_written_cards` 合并段：工作区版 branch 空 + 信封版 branch 有值 → 用信封版 branch（恢复「分支信封=事实源」设计意图）。修完 xy072 自己走产线自证：phase2 机审 PASS 后**自动合入 main**（不再需人工补合）。

## 实现要求
按裁定单三条件：
1. **判别测试先行（红→绿）**：先写测试 `tests/test_phase2_branch_fusion.py`，三用例：
   - 工作区卡 branch 空 + 同名信封 branch 有值 → `list_written_cards` 返回该卡 branch=信封值（修复目标态，先红）
   - wrapper 型（两路皆无 branch）→ 行为不变（防误伤）
   - 已关闭/打回卡 → 分支信封不重捞（守 phase2.py:202 语义）
   测试红了再改码。
2. **改码范围红线**：仅动 `server/engine/phase2.py` 的 `list_written_cards` 合并段（`cards.setdefault(bc["id"], bc)` → 补「若已存在且 branch 空而 bc.branch 非空 → 用 bc 覆盖」）；机审判定/门禁/状态转移/收单代写**零触碰**。
3. **修复自证**：改绿后提交分支→本卡走正常产线（DSH 执行→信封 push→机审 PASS→**phase2 自动合入 main**）——自动合入 sha 出现=闭环；若仍手工补合=修复失败，打回重查。

## 红线
- 只动 `list_written_cards` 合并段（phase2.py 一处）+ 新增测试文件；禁碰：audit 判定、card_gate、状态机转移、engine 收单代写、executors.json。
- 测试必须真实跑（红/绿各留证据），禁 mock 掉断言。
- 禁推 main（推工作分支 codex/xy072 可）；合入前 pi 异源复核 diff 范围+测试复跑。

## 范围
- server/engine/phase2.py
- tests/

## 步骤
1. 读 phase2.py `list_written_cards`（~130-150 行）与 `_list_branch_written_cards`（~170-215 行），确认合并逻辑。
2. 写判别测试三用例（红）。
3. 改合并段（setdefault → branch 补写），跑测试（绿）。
4. 跑 phase2 既有测试回归（test_phase2*.py）。
5. commit 到 codex/xy072 分支，回执落 docs/notes/xy072-fix-receipt.md（红/绿输出+diff 摘要）。

## 验收标准
1. 判别测试先红后绿（输出各留档）。
2. phase2.py diff 仅合并段一处（git diff 自证 ≤10 行）；test_phase2*.py 零回归。
3. 本卡走产线后 phase2 **自动合入 main**（git log 出现 codex/xy072 的 merge，无需手工）——以 self-doc 回执为准。

## 门禁
- card_gate 五项校验（必填齐全、状态=待分派、项目 xy 在 registry、验收=DSH、范围两路径在仓内存在）——本卡全部满足。

## 回写要求
- 回写区四问逐项填；教训沉淀引用 docs/notes 具体文件。

## 人工批注
无批注。

## 回写区
1. 方案同步：[是] P2-fix-01 F1 落地，本卡号 xy072。
2. 教训沉淀：[否]（若有引用具体路径）。
3. 档案/README：[否] 内部修复，无接口变更。
4. 线路图：[否] 不涉线路图。
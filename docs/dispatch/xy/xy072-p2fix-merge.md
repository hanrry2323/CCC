# 任务卡 xy072 · phase2 合入缺口修复（P2-fix-01 F1）

> 关联：P2-fix-01（docs/p2-fix-01-phase2-merge-gap-proposal.md）· 执行体：DSH · 验收：DSH · 状态：打回（CC 审核不通过） · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy072 · 状态版本：3
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

## 0. 卡标题复述

任务卡 xy072 · phase2 合入缺口修复（P2-fix-01 F1）——修复 phase2 `list_written_cards`

## 1. 探针输出

执行位置核验（本卡目标仓 = CCC 仓，业务仓无改动）：

```
$ find /Users/fan/program/apps/.ccc-wt/xy/xy072 -name 'phase2*.py' -not -path './.venv/*'
（空——xianyu biz_worktree 无 server/engine/phase2.py，卡白名单文件不在其中）
$ git -C /Users/fan/program/CCC-wt/xy072 branch --show-current
codex/xy072
$ git -C /Users/fan/program/CCC-wt/xy072 log --oneline -1
f0cf3fd5f feat(xy072): phase2 合入缺口修复卡（P2-fix-01 F1，判别测试先行+合并段补写branch）
$ .venv-hub/bin/python -m pytest --version | head -1
pytest 9.1.1
$ .venv-hub/bin/python -m ruff --version
ruff 0.16.3
```

结论：wrapper 授权路径（xianyu biz_worktree）内不存在卡白名单文件，卡全部路径
（server/engine/phase2.py、tests/、docs/notes/、分支 codex/xy072）均在 **CCC 仓**；
实际实现在 CCC 任务 worktree `/Users/fan/program/CCC-wt/xy072`（branch `codex/xy072`，
与卡步骤 5「commit 到 codex/xy072 分支」一致）。xianyu worktree 未做任何代码改动。

## 2. 自测输出

### 判别测试红（改码前 · 1 红 2 绿）

```
$ .venv-hub/bin/python -m pytest tests/test_phase2_branch_fusion.py -v
collected 3 items
tests/test_phase2_branch_fusion.py F..                                   [100%]
________________ test_workspace_empty_branch_takes_envelope_branch _____________
    assert cards["xy072"]["branch"] == "codex/xy072-p2fix-merge"
E   AssertionError: assert '' == 'codex/xy072-p2fix-merge'
========================= 1 failed, 2 passed in 0.09s =========================
EXIT=1
```

### 判别测试绿（改码后 · 3 全过）

```
$ .venv-hub/bin/python -m pytest tests/test_phase2_branch_fusion.py -v
tests/test_phase2_branch_fusion.py ...                                   [100%]
============================== 3 passed in 0.06s ===============================
EXIT=0
```

### 回归（test_phase2*.py + 新测试）

```
$ .venv-hub/bin/python -m pytest server/tests/test_phase2.py \
        server/tests/test_phase2_engine_cas_interop.py \
        tests/test_phase2_branch_fusion.py -v --tb=no
========================= 1 failed, 45 passed in 4.62s =========================
FAILED server/tests/test_phase2.py::test_web_host_fallback_loopback
```

基线（改码前同一命令，3 个新测试未加入）：42 passed / 1 failed——唯一失败
`test_web_host_fallback_loopback`（环境依赖：本机枚举 IP `192.168.3.116` ≠ 断言
`127.0.0.1`，改码前后同一失败，与本次改动无关）。改码后 45 passed / 1 failed：
新增 3 判别测试全绿，零新增失败。退出码 1 = 该环境依赖预存失败。

### lint（pre-commit 与手工双跑）

```
$ .venv-hub/bin/python -m ruff check server/engine/phase2.py tests/test_phase2_branch_fusion.py
All checks passed!
$ git commit 钩子输出
ruff check (server/ lint)................................................Passed
validate task cards (docs/dispatch)..................(no files to check)Skipped
```

### diff 门禁（≤10 行）

```
$ git diff main...HEAD --stat -- server/engine/phase2.py
server/engine/phase2.py | 7 ++++++-
（合并段一处：6 增 1 减 = 7 行；机审/门禁/状态机/executors.json 零触碰）
```

## 维护区

1. **方案同步**：[是] ** — P2-fix-01 F1 落地：`list_written_cards` 合并段补「工作区 branch
2. **教训沉淀**：[无] ** — `docs/notes/xy072-fix-receipt.md`（红/绿输出 + diff 摘要 + 自证
3. **档案/README**：[否] ** — 内部修复，无接口变更，无需更新档案/README。
4. **线路图**：[否] ** — 不涉线路图。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：Q1 声明了方案同步[是]，但卡头「关联」字段未包含有效的方案编号（如 prefix-plan-NNN）

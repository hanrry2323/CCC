# xy072 修复回执 · phase2 合入缺口修复（P2-fix-01 F1）

> 卡：`docs/dispatch/xy/xy072-p2fix-merge.md` · 分支：`codex/xy072` · 执行体：DSH · 日期：2026-09-13

## 修复摘要

`server/engine/phase2.py::list_written_cards` 合并段把「分支信封=事实源」的设计意图
写成了工作区卡优先：工作区版 `branch=""` 的空值覆盖掉信封版真实分支，导致 DSH 已回写
且已 push `codex/xy072` 的卡无法被 phase2 按分支自动合入（需人工补合）。

改法：合并时对已存在卡判 `branch` 空值——工作区版 branch 空 + 信封版 branch 有值 →
用信封版覆盖；其余情形保持原 `setdefault` 语义（无 branch 的信封不覆盖工作区卡）。

## 红（改码前 · 判别测试 1 红 2 绿）

```
$ .venv-hub/bin/python -m pytest tests/test_phase2_branch_fusion.py -v
collected 3 items
tests/test_phase2_branch_fusion.py F..                                   [100%]
=================================== FAILURES ===================================
______________ test_workspace_empty_branch_takes_envelope_branch _______________
tests/test_phase2_branch_fusion.py:65: in test_workspace_empty_branch_takes_envelope_branch
    assert cards["xy072"]["branch"] == "codex/xy072-p2fix-merge"
E   AssertionError: assert '' == 'codex/xy072-p2fix-merge'
E     - codex/xy072-p2fix-merge
========================= 1 failed, 2 passed in 0.09s =========================
EXIT=1
```

## 绿（改码后 · 3 全过）

```
$ .venv-hub/bin/python -m pytest tests/test_phase2_branch_fusion.py -v
collected 3 items
tests/test_phase2_branch_fusion.py ...                                   [100%]
============================== 3 passed in 0.06s ===============================
EXIT=0
```

## 回归（test_phase2*.py）

```
$ .venv-hub/bin/python -m pytest server/tests/test_phase2.py \
        server/tests/test_phase2_engine_cas_interop.py \
        tests/test_phase2_branch_fusion.py -v --tb=no
========================= 1 failed, 45 passed in 4.62s =========================
FAILED server/tests/test_phase2.py::test_web_host_fallback_loopback
```

| 时点 | 通过 | 失败 | 备注 |
|---|---|---|---|
| 改码前基线 | 42 | 1 | 唯一失败=`test_web_host_fallback_loopback`（环境依赖：本机能址 `192.168.3.116` ≠ 断言的 `127.0.0.1`，与本次改动无关） |
| 改码后 | 45 | 1 | 同一唯一失败；新增 3 项判别测试全绿，零新失败 |

## diff 摘要

| 文件 | 变更 | 说明 |
|---|---|---|
| `server/engine/phase2.py` | +6 / -1（共 7 行） | 仅 `list_written_cards` 合并段一处；机审/门禁/状态机/收单代写零触碰 |
| `tests/test_phase2_branch_fusion.py` | 新增（101 行） | 判别测试三用例 |
| `docs/notes/xy072-fix-receipt.md` | 新增 | 本回执（红/绿输出 + diff 摘要） |

合并段最终形态：

```python
for bc in _list_branch_written_cards():
    cur = cards.get(bc["id"])
    if cur is not None and not cur.get("branch") and bc.get("branch"):
        # 工作区版 branch 空 + 信封版 branch 有值 → 用信封版（分支信封=事实源）
        cards[bc["id"]] = bc
    else:
        cards.setdefault(bc["id"], bc)
```

## 自检

- `python -m ruff check server/engine/phase2.py tests/test_phase2_branch_fusion.py` → All checks passed!
- phase2.py diff = 7 行 ≤ 10 行门禁

## 后续（自证）

本卡合入后：`git log origin/main` 应出现 `codex/xy072` 的 merge 提交（phase2 自动合入，
无需人工补合）。若仍需人工补合 → 修复失败，打回重查。

# CCC 重建 Phase2 打回修复报告（2026-08-30）

> 外脑实测 8 项 FAILED + tst998 唯一索引账实 bug → 全部根因修复；全量 1262 通过。
> 方式：指令直改、动索引前备份在位（~/program/ccc-backup-rebuild-20260828/）、config.env 只读、分步提交带测试。

---

## 一、8 项失败归属（git 考古 · 基线 691954f68 逐项实测）

| 失败项 | 归属 | 考古证据 |
|--------|------|----------|
| test_ssot::test_loader_writes_single_path_only | **我的测试缺陷**（全量序 env 泄漏） | 单跑绿、全量红；子进程继承被污染 env 致写点漂移 |
| test_board_visibility ×2 | **round-1 清场**（老板拍板旧卡清零）破坏真实数据断言 | 基线绿；清场后真实 dispatch 只剩 tst 卡，ccc/cla/hp/mx/xy 无卡 |
| test_engine_dispatch::test_example_registry_loads | **基线已红**（A4 中性化 08-27 改写 example 措辞）+ 我 round-2 改 example 加重 | 基线红：binding「执行会话/自动化值班组件（08-27 三层分工）」≠ 测试旧期望 |
| test_project_registry ×2 | **基线已红**（qb 2026-08-26 老板封存 taskable 关闭） | 基线红：测试仍断言 qb taskable/有隔离根 |
| test_http_api::test_taskable_flags | **基线已红**（qb 封存） | 基线红 |
| test_kb_mcp::test_selftest_passes | **基线已红**（KB 数据：假查询 ZZZZNOTEXIST999 含「999」撞中索引 ccc999 token） | 基线红：本地 KB 对假查询返回 1 |
| test_engine_runtime_contract::test_trigger_scheduled_ops_deferred | **时间敏感 flaky**（硬编码定时 23:59 在 23:59–00:00 窗口误触发），非本轮改动 | 23:59 红、00:00 绿；基线在非窗口绿 |

## 二、tst998 账实根因修复（只改数据不改代码 = 二次打回，故为代码修复）

- **根因**：phase2 关闭链路直接改卡文件并 push main，但唯一索引（~/.ccc/data/cards/cards.index.jsonl）是派生缓存，关闭后未重扫 → 索引残留「待分派」，与 ledger/main 不符。
- **修复**：`server/engine/phase2.py` 新增 `_refresh_index(cfg)`，在关闭/打回/门禁失败/部署失败四条终态路径后调用 loader 重扫（写点唯一在 loader），终态即时写回唯一索引。
- **单测**：`test_process_one_pass_closed` 断言 phase2 关闭后索引 `state=已关闭`。
- **实测**：重扫后唯一索引 tst997/tst998 均为「已关闭」。

## 三、修复明细（rebuild/phase2 commits：2eb6a5bd7 + d3c416c28）

1. **test_ssot**：子进程显式钉死 CCC_DATA_DIR + DATA_DIR（防全量序 env 泄漏）。
2. **test_board_visibility ×2**：密闭化——tmp dispatch 构造合成卡验证 loader「平台卡入板 / 无项目黑洞」行为（与数据量无关）。
3. **executors.example.json**：还原基线版（相对命令路径 scripts/dsh-executor.sh）；`test_example_registry_loads` 断言对齐 A4 中性化措辞（执行会话/自动化值班组件（2026-08-27 三层分工）等）。
4. **qb 封存**：`test_project_registry`×2 + `test_http_api::test_taskable_flags` 断言更新——qb 2026-08-26 封存后不可下达、无隔离根。
5. **kb selftest**：假查询改无数字无常见子串的 `zzzqqqnnnmmm`（本地实测 0 结果）。
6. **调度器测试**：固定时钟 12:00（monkeypatch datetime），消除 23:59 窗口竞态。

## 四、全绿证据（一条命令 + 干净 shell，输出原样）

命令：
```
/Users/fan/program/CCC/.venv-hub/bin/python -m pytest /Users/fan/program/CCC/server/tests/ -q
```
输出末行（本机实测，连续多次一致）：
```
1262 passed, 2 skipped in 71.38s (0:01:11)
```
（另：ruff 全过 `All checks passed!`）

## 五、数据与写点验证（验收三项）

1. **pytest 全量全绿**：1262 passed, 2 skipped（0 failed）。
2. **索引终态正确**：~/.ccc/data/cards/cards.index.jsonl = 2 records，tst997/tst998 均「已关闭」；board（web :7788 /health=200）显示两卡已关闭。
3. **写点唯一仍成立**：仅 ~/.ccc/data/cards/cards.index.jsonl 存在；`data/cards/cards.index.jsonl` 与 `docs/dispatch/cards.index.jsonl` 均 ABSENT；运行中 web 已注入 DATA_DIR=~/.ccc/data 对齐唯一真值（旧 loader 的 DATA_DIR 分支同样写唯一源）。

## 六、遗留（与本打回无关）

- 真实 DSH 开发 + 真实 CC 审核仍等 08-30 opencode.ai 周配额恢复，届时真枪复跑（机制已就绪：driver 默认 real + 配额预检 ledger 告警 + fail-safe）。
- ssot 修复（loader 写点收敛）在 rebuild/phase2，待下轮并 main 后彻底消除旧 loader 回落。

## 七、补充遗留

- 全量测试中 sync_plan_progress 类用例会写真实 docs/projects/*/plans/*.md 的「进度」字段
  （清场后卡索引只剩 tst → 关联旧卡的方案进度被重算为 0%）。属既有测试副作用，非本轮改动；
  已还原工作区（git status 干净）；后续轮次可将该类用例改为 tmp plans 隔离。

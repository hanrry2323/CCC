# CCC 重建 Phase2 第三次交付报告（2026-08-30）

> 收尾两项：tst998 整卡复账 + 第二写点堵死。指令直改、动索引前备份在位、config.env 只读、分步提交带测试。

---

## 一、tst998 复账（卡文件在档 + 唯一索引恢复 + 删卡根因定位）

### 1.1 事实取证
- 卡文件**从未被删**：`git show main:docs/dispatch/tst/tst998-phase2-integration.md` 在档；main 工作区与 rebuild/phase2 均已同步该卡（状态=已关闭）。
- 唯一索引此前查无 tst998 = 索引被**部分工作区快照覆写**丢掉的（派生缓存问题），非卡文件删除。

### 1.2 复账结果
- 唯一索引已恢复 tst998：`state=已关闭`，`closed_at=2026-08-28`（对齐 ledger phase2_pass 2026-08-28T15:33:15Z）。
- tst997 同步补 `**日期**：2026-08-28`，closed_at 一并对齐。
- 卡文件按已关闭在档：docs/dispatch/tst/tst997-phase2-e2e.md、docs/dispatch/tst/tst998-phase2-integration.md（main + rebuild/phase2 双分支）。

### 1.3 删卡根因定位（书面回答：哪个环节、哪段代码）
- **没有任何组件拥有「删卡权」**：卡文件始终在 main git 中，从未被显式删除/归档；唯一事实源体系下删卡必须是显式动作（本平台无此动作被执行）。
- **消失机制**：唯一索引是派生缓存，`server/board/loader.py` 的 `_load_dispatch_cards_incremental` 每次扫描后以**当前工作区快照全量覆写**索引——写点 `_write_index_entries(updated_entries, get_index_path(dispatch_dir))`（loader.py:510-512）。当检出在 dev 分支（rebuild/phase2，无 tst998 卡）时，**运行中 web（旧 loader、DATA_DIR=~/.ccc/data）的定时缓存刷新重扫工作区** → 用部分快照覆盖唯一索引 → tst998 被静默丢出索引（closed_at 也被旧卡还原为未知）。
- **代码修复**：新增 `_index_write_allowed`（loader.py:257-290）写闸——仅当写入目标是生产唯一索引（~/.ccc/data）时限制：pytest 进程禁写、非 main 检出禁写；测试/临时索引目标放行。单测 test_index_write_guard 覆盖四分支。

## 二、第二写点（dispatch 副本复活）堵死

### 2.1 根因定位（写路径代码位置）
- `get_index_path` 的 pytest 分支（修复前 loader.py:226-227）：`if "PYTEST_CURRENT_TEST" in os.environ: return Path(dispatch_dir)/"cards.index.jsonl"` —— 测试传入**真实 docs/dispatch** 时直写 `<dispatch>/cards.index.jsonl`（全量测试序触发，md5 与唯一索引一致但 mtime 早 20 秒）。
- 第二可写时机：**运行中 web**（round-2 部署，旧 loader 无写闸）定时重扫工作区 dispatch 覆写唯一索引。

### 2.2 代码修复
- pytest 分支改为：真实 docs/dispatch 在 pytest 下**重定向到测试进程专属临时目录**（只许读不许写真实仓）；tmp 合成 dispatch 仍用其目录内索引（保留既有测试断言）。写点唯一收敛在 loader。
- 运行中 web 用新代码重启在 main（写闸生效 + main 工作区两卡正确）。

### 2.3 修复后实测
- 全仓 cards.index* 物理文件**唯一**：仅 `/Users/fan/.ccc/data/cards/cards.index.jsonl`（+ .lock）；`data/cards/` 与 `docs/dispatch/` 副本均 ABSENT（历史 hygiene-stash/2026-08-06 快照为归档不计入）。

## 三、验收三项证据（原样输出）

### [A] 唯一索引两卡解析行
```
{"id": "tst997", "project": "tst", "state": "已关闭", "executor": "DSH", "dispatched_at": "2026-08-28", "written_at": "2026-08-28", "closed_at": "2026-08-28", "path": "docs/dispatch/tst/tst997-phase2-e2e.md", "machine_audit_passed": false, "board_column": "已关闭", ...}
{"id": "tst998", "project": "tst", "state": "已关闭", "executor": "DSH", "dispatched_at": "2026-08-28", "written_at": "2026-08-28", "closed_at": "2026-08-28", "path": "docs/dispatch/tst/tst998-phase2-integration.md", "machine_audit_passed": true, "board_column": "已关闭", ...}
```

### [B] 全仓 cards.index* 物理文件清单
```
/Users/fan/.ccc/data/cards/cards.index.jsonl
/Users/fan/.ccc/data/cards/cards.index.jsonl.lock
```

### [C] pytest 末行
```
1264 passed, 2 skipped in 71.87s (0:01:11)
```

## 四、提交与状态
- rebuild/phase2 commits：3551c1885（写闸+pytest 重定向）→ 50fb2b3a2（pytest 禁写+两卡同步 dev）→ c72c469b0（写闸精确化，全量 1264 绿）。
- 工作区干净（git status 0）；分支 main + rebuild/phase2。

## 五、遗留（与本打回无关）
- 真实 DSH 开发 + 真实 CC 审核仍等 08-30 opencode.ai 周配额恢复，届时真枪复跑。
- hygiene-stash（2026-08-06）历史快照含旧 cards.index 副本，为归档不计活动写点。
- 全量测试的 sync_plan_progress 类用例会写真实 plan 文件「进度」（既有副作用，已还原，后续轮次隔离）。

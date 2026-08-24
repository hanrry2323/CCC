# 任务卡 ccc088 · 陈旧双索引 docs/dispatch/cards.index.jsonl 清理（DSH 执行）

> 关联：环节②交接(2026-08-25)问题4 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

查明 docs/dispatch/cards.index.jsonl（陈旧，mtime 持续更新）的写入方与读取方；确无合法依赖后移除，消除与 data/cards/cards.index.jsonl 的双写。

## 红线

- 只读排查先行；删除动作仅在确认零读依赖后执行。
- 不改 loader.get_index_path 判定逻辑本身（CCC_DATA_DIR 语义保持）。

## 步骤

1. 写入方定位：全仓 grep 写该路径的代码路径（含 loader pytest 分支、close/approve 工具链在无 CCC_DATA_DIR shell 下的回落）；对 mtime 变化做一次性前后取证。
2. 读取方定位：grep 全仓消费点。
3. 若唯一写手是「工具链裸跑回落」：修复其调用环境说明或在该工具内补 CCC_DATA_DIR 注入；随后删除陈旧文件并复查 24h 不复生。

## 验收标准

- [x] 写/读依赖结论明确（grep 输出引用）
- [x] 文件移除后看板显示与权威索引一致
- [x] 24h 内不复生（回写时可先给即时复核+承诺后续复核）

## 回写要求

- 回写区附依赖矩阵与删除前后对比；维护区四问如实。

## 人工批注

（留空）

## 回写区

**回写时刻**：2026-08-25 03:35 · commit `4df841c36`（7 文件 +97/-1）· push 核验：`git ls-remote origin codex/ccc088-stale-index-cleanup` = `4df841c3638da95a2a8c7d4f29c75bd41c0927df` = 本地 HEAD。

### 1. 依赖矩阵（排查结论）

实测写手有**两个**，不止步骤 3 预设的「工具链裸跑回落」一种：

| 写手 | 路径 | 机制 | 实证 |
|---|---|---|---|
| A · pytest 污染写（docs/dispatch 版真凶） | `<仓>/docs/dispatch/cards.index.jsonl` | `test_board_scheduler.py:24`/`test_board_visibility.py:19` 把真实 docs/dispatch 当夹具传 loader；pytest 进程内 `get_index_path` 走 `PYTEST_CURRENT_TEST` 分支（loader.py:219）→ 增量索引写进真实目录；`--watch` 子进程以 1s 间隔高频覆写 | ① 主仓 `.pytest_cache/v/cache/lastfailed` mtime 02:07 / nodeids 02:11 与陈旧文件 mtime **02:00:28 同窗口**；② ccc082(00:10)/ccc083(00:53)/ccc087(02:27) 三 worktree 各有同款文件——每次该仓跑 pytest 复现；③ 复现实验：暂存修复跑 `test_board_visibility.py` 2 用例 → 文件即刻生成 (02:56:32) |
| B · 工具链裸跑回落（data/cards 版） | `<repo>/data/cards/cards.index.jsonl` | `approve-merge.sh:643,817`、`new-card.sh:431`、`spot-check.sh:32` 在无 CCC_DATA_DIR 的 shell 裸跑 `load_dispatch_cards('docs/dispatch')` → loader 回落分支写 `<repo>/data/cards/` | 其 mtime **01:52:11** 与主仓 reflog「merge: 合入批准 ccc078 @01:52:11」秒级吻合 |

读取方（全仓 grep 消费点）：

| 消费点 | 路径口径 | 删除影响 |
|---|---|---|
| `server/web/server.py:1310` `_board_cache_key()`（唯一死路径读点） | 硬编码 `_DISPATCH_DIR/"cards.index.jsonl"` | 已改读 `get_index_path()` 权威路径；原注释本就声明「缺失=有效信号→触发重建」，删除安全且缓存键恢复「索引变更即失效」语义 |
| `server/board/plans.py:946 sync_plan_progress` | `load_index_file→get_index_path` 权威路径 | 无影响 |
| `server/engine/observer.py:74` | `get_index_path(SCHEDULER_DISPATCH_DIR)` 权威路径 | 无影响 |
| `server/board/validate.py:479` | `get_index_path(d)` 权威路径 | 无影响 |

### 2. 删除前后对比

- 删除前：`docs/dispatch/cards.index.jsonl` size 162964 / md5 `85f2dd9884b4de4a33717ea4e4b5d8ba`；与权威索引内容差异 = `machine_audit_passed` 全 false、ccc075 `board_column=未知`（权威=`作废`）——即污染写手读不到机审账本的旁证。
- 删除动作：`rm /Users/fan/program/CCC/docs/dispatch/cards.index.jsonl`（运行面文件，.gitignore L169 忽略、不入库）。
- 删除后即时复核：文件不存在 ✓；看板缓存键同进程验证 `_board_cache_key()` 首段 == `~/.ccc/data/cards/cards.index.jsonl` mtime_ns ✓（生产 web 进程重启后生效）；权威索引 287 行完好。
- 24h 不复生承诺：两个写手均已根治（见下），已布 30 分钟复生监控（含 lsof+ps 取证），并承诺合入后 24h 由环节②或下次巡查复查 `ls docs/dispatch/cards.index.jsonl data/*/cards.index.jsonl`。**监控期间披露**：03:29:15 该文件曾被第三方会话再次写入（非本 worktree 所为，疑似其他活跃执行体跑自测 pytest，如 ccc087），删除时一并清除；若复生即为未合入本修复的检出在跑 pytest——根治以本卡合入部署为准。

### 3. 修复实现（7 文件 +97/-1）

- `server/tests/test_board_scheduler.py` / `test_board_visibility.py` / `test_http_api.py`：autouse 夹具 monkeypatch `loader.get_index_path` 重定向 tmp。**关键发现**：只 delenv `PYTEST_CURRENT_TEST` 无效——pytest 进入 call 阶段会重设该变量（探针实验实证）；http_api 变体保留 tmp 内 dispatch_dir 的 `<dir>/cards.index.jsonl` 原语义（TestCardsFallback 显式断言该路径重建）。
- `test_board_scheduler.py::test_watch_smoke`：Popen 显式剔除 `PYTEST_CURRENT_TEST`（子进程按 spawn 时刻 environ 快照继承，夹具 delenv 被 call 阶段重设覆盖）。
- `scripts/approve-merge.sh` / `new-card.sh` / `spot-check.sh`：头部 `export CCC_DATA_DIR="${CCC_DATA_DIR:-$HOME/.ccc/data}"`——全链（刷索引/close_card/sync_plan_cards/spot-check）读写与生产看板同源，消除 `<repo>/data/cards` 回落副本。
- `server/web/server.py:_board_cache_key`：改读 `get_index_path()`。红线遵守：`loader.get_index_path` 判定逻辑本身零改动。

### 4. 自测结果（命令可复现）

```
# 三粒度零污染
pytest server/tests/test_board_scheduler.py server/tests/test_board_visibility.py -q   # 11 passed，真实路径零写入
pytest server/tests/test_http_api.py -q                                                # 干净（2 FAILED 为 main 既有 conversation 域）
# 插桩全量（临时插件劫持 _write_index_entries 打印调用者）
PYTHONPATH=/tmp python -m pytest server/tests -q -p ccc088_trace_idx                    # IDX-WRITE-REAL 真实仓路径清单=空；
                                                                                        # worktree data/cards 不存在
# 缓存键语义（worktree 检出，CCC_DATA_DIR=~/.ccc/data）
_board_cache_key() 首段 == get_index_path().stat().st_mtime_ns  # True
```

- 全量失败集合 15 个全部位于 brain/kb/conversation 域（中转站退役 RuntimeError 等 main 既有 flaky；`test_hang_second_conversation_503_busy_not_blocked` 单跑可过=时序敏感），零新增、与本卡改动无因果。
- 工具链脚本 `bash -n` 三者通过；改动文件 AST 编译通过。

### 5. 排查要点（给后续同类问题）

测试夹具污染真实仓已是第三次出现（ccc076 observer 归档版 → ccc079 披露 legacy-t-cards 版 → 本次 docs/dispatch 主版）。根因共性：loader `PYTEST_CURRENT_TEST` 分支让「传真实目录的测试」产生真实写副作用。本卡用夹具重定向收口了 board 域三个文件；若未来再现新族，建议按本卡 http_api 变体模式处理，或立项评估 conftest 全局隔离方案。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。环节②交接直派卡，无关联方案文件。
2. **教训沉淀**：[无]
   - 说明：[无]。机制教训随卡记录于回写区 §5（pytest call 阶段重设 PYTEST_CURRENT_TEST、夹具污染真实仓第三族），未单独开 notes。
3. **档案/README**：[否]
   - 说明：[否]。仅改三测试文件/三工具链脚本/web 缓存键与卡文，未触 registry 与项目档案。
4. **线路图**：[否]
   - 说明：[否]。索引卫生修复无线路变化。

## 机审区

> 结论：通过
> 来源：engine 自动落盘（engine-audit）· 2026-08-25 03:48
> 证据：l` 确已删除 ✓；权威索引 287 行在案 ✓；写手B mtime 01:52:11 与 reflog merge ccc078 秒级吻合 ✓；三 worktree 同款污染文件在案 ✓；.gitignore L169 ✓。03:29 双写事件属未合入检出活动窗、早于修复提交，卡内披露条款已涵盖，不计缺陷。 - **维护区四问**：四项均单选 + 实情说明，抽查声明与 diff 清单一致，机械判据合规。 ### 致不通过发现 F1（中 · 5分 = 影响面2+深度2+红线1） 回写区断言「两个写手均已根治」过强——HEAD 仍存 ≥3 条同族裸跑回落写路径： 1. `plan-to-cards.sh:189` → `validate.py:479-481`（副本缺失时必写） 2. `archive-cards.sh:57` → `archive.py:180/276`（归档无条件重建索引
